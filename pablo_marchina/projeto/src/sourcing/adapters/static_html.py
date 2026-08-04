from __future__ import annotations

from hashlib import sha256
from urllib.parse import urlparse

from src.scraping.http_collector import HttpSourceCollector
from src.scraping.source_registry import SourceRecord as ScrapingRecord
from src.sourcing.adapters.base import EvidenceSpan, SourceAdapter, SourceResult


def _get_default_collector() -> HttpSourceCollector:
    """Return a module-level shared collector (lazy init)."""
    global _DEFAULT_COLLECTOR
    if _DEFAULT_COLLECTOR is None:
        _DEFAULT_COLLECTOR = HttpSourceCollector()
    return _DEFAULT_COLLECTOR


_DEFAULT_COLLECTOR: HttpSourceCollector | None = None


def _scraping_result_to_source_result(
    scraping_result,
    target: str,
    *,
    max_evidence_length: int = 2000,
) -> SourceResult:
    """Map a scraping SourceFetchResult back to a sourcing SourceResult."""
    if scraping_result.status in ("fetched", "cached", "stale"):
        raw = scraping_result.raw_text or scraping_result.raw_html or ""
        text = scraping_result.extracted_text or raw
        # Build one headline evidence span from the scraped content
        span = EvidenceSpan(
            text=text[:max_evidence_length],
            source_url=target,
            confidence=0.7 if scraping_result.status == "fetched" else 0.5,
        )
        return SourceResult(
            target=target,
            status="collected",
            raw_text=text,
            evidence_spans=[span],
            content_hash=sha256(text.encode("utf-8")).hexdigest(),
        )
    if scraping_result.status == "blocked":
        return SourceResult(
            target=target,
            status="blocked",
            raw_text="",
            error=scraping_result.error_message_sanitized or "Source blocked by compliance rules",
        )
    return SourceResult(
        target=target,
        status="failed",
        raw_text="",
        error=scraping_result.error_message_sanitized or scraping_result.error_code or "Scraping failed",
    )


class StaticHtmlAdapter(SourceAdapter):
    """Collect static HTML pages using the governed scraping pipeline.

    Uses HttpSourceCollector internally (with cache, rate limiting, robots.txt,
    retry/backoff) instead of raw urllib.
    """

    source_type = "static_html"
    _default_collector_type = "http"

    def __init__(
        self,
        collector: HttpSourceCollector | None = None,
        collector_type: str | None = None,
    ):
        self._collector = collector or _get_default_collector()
        self._collector_type = collector_type or self._default_collector_type

    def _build_scraping_record(self, target: str) -> ScrapingRecord:
        parsed = urlparse(target)
        domain = parsed.netloc or target.replace("/", "_").replace(":", "_")
        # Strip leading www. for cleaner ids
        source_id = domain.removeprefix("www.").replace(".", "_")
        return ScrapingRecord(
            source_id=source_id or f"inline_{sha256(target.encode()).hexdigest()[:12]}",
            source_name=target,
            source_category="official_website",
            base_url=target,
            collector_type=self._collector_type,
        )

    def collect(self, target: str) -> SourceResult:
        """Collect content from *target* URL.

        Delegates to the governed scraping pipeline which handles:
        - Disk cache (diskcache with TTL per freshness policy)
        - Rate limiting (per policy ID, with backoff)
        - robots.txt compliance
        - Retry with exponential backoff
        - Duplicate detection (exact hash + fuzzy)
        - HTML→text extraction (trafilatura / BeautifulSoup)
        """
        record = self._build_scraping_record(target)
        fr = self._collector.collect_one(record)
        return _scraping_result_to_source_result(fr, target)
