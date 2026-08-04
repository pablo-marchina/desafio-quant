from __future__ import annotations

import re
from typing import Any

from src.discovery.source_registry import DiscoverySource
from src.scraping.scrapers.base_scraper import SourceScraper


class AceScraper(SourceScraper):
    source_id = "ace_startups_portfolio"

    def extract_entries(self, html: str, source: DiscoverySource) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for match in re.finditer(
            r"(?:startup|portfolio|empresa)\s*[:\-]\s*([A-Z][A-Za-z0-9\s\.]+)",
            html,
            re.IGNORECASE,
        ):
            name = match.group(1).strip()
            entries.append({"name": name, "source_id": self.source_id})
        return entries
