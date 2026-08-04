from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from src.discovery.source_registry import DiscoverySource
from src.scraping.fetcher import fetch_page
from src.scraping.parser import extract_clean_text

scraper_registry: dict[str, type[SourceScraper]] = {}


class SourceScraper(ABC):
    source_id: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        sid = getattr(cls, "source_id", None)
        if sid:
            scraper_registry[sid] = cls

    @abstractmethod
    def extract_entries(self, html: str, source: DiscoverySource) -> list[dict[str, Any]]: ...

    def scrape(self, source: DiscoverySource) -> list[dict[str, Any]]:
        if not source.base_url:
            return []
        time.sleep(1.0 / max(source.rate_limit_hint, 1))
        result = fetch_page(source.base_url)
        if result.error:
            raise RuntimeError(f"fetch_failed: {result.error}")
        if not result.raw_html:
            return []

        # HTML-aware scrapers need the original markup to retain anchors/URLs.
        # Regex-only scrapers can still fall back to clean text when no HTML
        # candidates are extracted.
        entries = self.extract_entries(result.raw_html, source)
        if entries:
            return entries
        text = extract_clean_text(result.raw_html)
        return self.extract_entries(text, source)
