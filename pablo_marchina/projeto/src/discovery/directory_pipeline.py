from __future__ import annotations

import logging
from typing import Any

from src.scraping.directory_extractor import extract_startups
from src.scraping.directory_paginator import paginate
from src.scraping.http_collector import HttpSourceCollector
from src.scraping.source_registry import SourceRecord

logger = logging.getLogger(__name__)


class DirectoryPipeline:
    """Full pipeline: paginate -> extract -> collect each startup."""

    def __init__(
        self,
        collector: HttpSourceCollector | None = None,
    ):
        self._collector = collector or HttpSourceCollector()

    def run(
        self,
        directory_sources: list[SourceRecord],
    ) -> list[dict[str, Any]]:
        """Run the directory pipeline and return extracted startup candidates.

        Returns:
            List of candidate dicts with keys:
                ``name``, ``url``, ``source_id``, ``description``
        """
        candidates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for source in directory_sources:
            source_id = source.source_id
            base_url = source.base_url or ""

            page_urls = paginate(source_id, base_url)
            logger.info("Directory %s: %d page(s) to scrape", source_id, len(page_urls))

            for page_url in page_urls:
                page_source = source.model_copy(update={"base_url": page_url})
                fr = self._collector.collect_one(page_source)
                if fr.status not in ("fetched", "cached"):
                    continue

                entries = extract_startups(source_id, fr.raw_html, base_url)
                for entry in entries:
                    url = entry.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        candidates.append({
                            "name": entry.get("name", ""),
                            "website": url,
                            "source_id": source_id,
                            "description": "",
                            "country": "Brazil",
                            "sector": "AI",
                        })

        logger.info("DirectoryPipeline: %d unique candidates extracted", len(candidates))
        return candidates

    def run_and_feed(self, directory_sources: list[SourceRecord]) -> dict[str, Any]:
        """Run pipeline and feed candidates into discovery system."""
        candidates = self.run(directory_sources)
        if not candidates:
            return {"status": "completed", "candidates_count": 0}

        try:
            from src.database.session import get_session
            from src.discovery.service import StartupDiscoveryService

            session = next(get_session())
            service = StartupDiscoveryService(session)
            result = service.run_manual_seed_discovery(
                seed_entries=candidates,
                source_id="directory_pipeline",
            )
            session.close()
            return result
        except Exception as exc:
            logger.exception("Failed to feed directory candidates into discovery")
            return {"status": "error", "error": str(exc), "candidates_count": len(candidates)}
