"""Bridge between Scrapy output and the governed scraping pipeline.

Allows feeding large-scale Scrapy crawl results (e.g. directory listings
with thousands of entries) into the existing extraction/analysis pipeline
without re-fetching every page through HttpSourceCollector.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.scraping.http_collector import SourceFetchResult

logger = logging.getLogger(__name__)


class ScrapyBridge:
    """Ingest Scrapy JSON output and yield SourceFetchResult-compatible dicts.

    Usage::

        bridge = ScrapyBridge()
        results = bridge.ingest("scrapy_output/startups.json")
        for r in results:
            print(r.source_url, r.status)
    """

    def ingest(
        self,
        scrapy_output_path: str | Path,
        *,
        source_id_prefix: str = "scrapy",
        max_items: int = 0,
    ) -> list[SourceFetchResult]:
        """Read Scrapy JSON Lines or JSON array and convert to SourceFetchResults.

        Expects each item to have at minimum a ``url`` or ``URL`` field.
        Optional fields: ``title``, ``text``, ``html``, ``status_code``.

        Args:
            scrapy_output_path: Path to Scrapy output file (.json or .jl).
            source_id_prefix: Prefix for generated source IDs.
            max_items: Max items to process (0 = all).

        Returns:
            List of SourceFetchResult objects ready for the extraction pipeline.
        """
        path = Path(scrapy_output_path)
        if not path.exists():
            logger.error("Scrapy output not found: %s", path)
            return []

        items = self._load_items(path)
        if max_items > 0:
            items = items[:max_items]

        results: list[SourceFetchResult] = []
        for i, item in enumerate(items):
            url = item.get("url") or item.get("URL") or ""
            if not url:
                continue

            title = item.get("title", "")
            text = item.get("text", item.get("body", ""))
            html = item.get("html", "")
            status_code = item.get("status_code", 200)

            fetched_at_str = item.get("fetched_at", "")
            try:
                fetched_at = datetime.fromisoformat(fetched_at_str) if fetched_at_str else datetime.now(UTC)
            except Exception:
                fetched_at = datetime.now(UTC)

            results.append(
                SourceFetchResult(
                    source_id=f"{source_id_prefix}_{i}",
                    source_url=url,
                    status="fetched",
                    http_status_code=status_code,
                    fetched_at=fetched_at,
                    raw_html=html or text,
                    raw_text=text or title,
                    extracted_text=text or title,
                    metadata={
                        "source_name": title,
                        "scrapy_item": True,
                        "original_index": i,
                    },
                    compliance_status="compliant",
                    robots_allowed=True,
                    latency_ms=0,
                    content_bytes=len((html or text).encode("utf-8")),
                    extraction_status="success" if text else "empty",
                )
            )

        logger.info("ScrapyBridge: ingested %d items from %s", len(results), path.name)
        return results

    @staticmethod
    def _load_items(path: Path) -> list[dict[str, Any]]:
        """Load items from JSON or JSON Lines file."""
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            return []

        # JSON Lines — one dict per line
        if raw.startswith("{"):
            return [json.loads(line) for line in raw.splitlines() if line.strip().startswith("{")]

        # JSON array
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        # Try wrapping bare dicts in array
        try:
            data = json.loads(f"[{raw}]")
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            logger.warning("ScrapyBridge: unable to parse %s", path)
            return []

        return []
