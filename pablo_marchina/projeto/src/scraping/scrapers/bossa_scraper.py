from __future__ import annotations

import re
from typing import Any

from src.discovery.source_registry import DiscoverySource
from src.scraping.scrapers.base_scraper import SourceScraper


class BossaScraper(SourceScraper):
    source_id = "bossa_invest_portfolio"

    def extract_entries(self, html: str, source: DiscoverySource) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for match in re.finditer(
            r"([A-Z][A-Za-z0-9\s\.]{2,50})\s*(?:[\(\)]|–|-|\|)",
            html,
        ):
            name = match.group(1).strip()
            if len(name) > 3:
                entries.append({"name": name, "source_id": self.source_id})
        return entries
