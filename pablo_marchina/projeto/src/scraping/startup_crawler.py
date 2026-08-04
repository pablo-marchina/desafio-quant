from __future__ import annotations

import logging
from typing import Any

from src.scraping.http_collector import HttpSourceCollector
from src.scraping.page_discovery import discover_pages
from src.scraping.source_registry import SourceRecord

logger = logging.getLogger(__name__)


def _url_to_source_record(url: str, collector_type: str = "http") -> SourceRecord:
    """Convert a URL to a minimal SourceRecord for the scraping engine."""
    from hashlib import sha256
    from urllib.parse import urlparse

    domain = urlparse(url).netloc or "unknown"
    source_id = sha256(url.encode()).hexdigest()[:12]
    return SourceRecord(
        source_id=source_id,
        source_name=url,
        source_category="official_website",
        base_url=url,
        collector_type=collector_type,
    )


class StartupCrawler:
    """Crawl a startup's online presence: official site, blog, careers, etc.

    Uses ``HttpSourceCollector`` internally so all governed scraping
    features (cache, rate limiting, robots, retry) are applied to every page.
    Results are keyed by URL for downstream processing.
    """

    def __init__(
        self,
        collector: HttpSourceCollector | None = None,
        *,
        max_pages: int = 10,
        crawl_depth: int = 1,
    ):
        self._collector = collector or HttpSourceCollector()
        self._max_pages = max_pages
        self._crawl_depth = crawl_depth

    def crawl(self, startup_url: str) -> dict[str, dict[str, Any]]:
        """Crawl *startup_url* and return collected pages keyed by URL.

        Returns:
            dict mapping page URL -> dict with keys:
                - ``status``: str  ("fetched", "cached", "blocked", "failed")
                - ``text``: str    (extracted clean text, or "" on failure)
                - ``html``: str    (raw HTML, or "" on failure)
                - ``error``: str | None
        """
        pages = discover_pages(startup_url, max_pages=self._max_pages, depth=self._crawl_depth)
        logger.info("Discovered %d page(s) for %s", len(pages), startup_url)

        results: dict[str, dict[str, Any]] = {}
        for url in pages:
            record = _url_to_source_record(url)
            fr = self._collector.collect_one(record)
            results[url] = {
                "status": fr.status,
                "text": fr.extracted_text or "",
                "html": fr.raw_html or "",
                "error": fr.error_message_sanitized,
            }

        # Always include the root URL if not already in results
        root = startup_url.rstrip("/")
        if root not in results:
            record = _url_to_source_record(root)
            fr = self._collector.collect_one(record)
            results[root] = {
                "status": fr.status,
                "text": fr.extracted_text or "",
                "html": fr.raw_html or "",
                "error": fr.error_message_sanitized,
            }

        return results
