from __future__ import annotations

import re
from typing import Any

from src.discovery.source_registry import DiscoverySource
from src.scraping.scrapers.base_scraper import SourceScraper


class DistritoScraper(SourceScraper):
    source_id = "distrito_startup_programs"

    def extract_entries(self, html: str, source: DiscoverySource) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        lines = [ln.strip() for ln in html.split("\n") if ln.strip()]
        current: dict[str, Any] = {}
        for line in lines:
            name_match = re.search(r"(startup|programa|aceleradora)\s*[:\-]\s*(.+)", line, re.IGNORECASE)
            if name_match:
                if current:
                    entries.append(current)
                current = {"name": name_match.group(2).strip(), "source_id": self.source_id}
                continue
            if re.search(
                r"(ai|ia|inteligencia artificial|machine learning|ml|llm)",
                line,
                re.IGNORECASE,
            ):
                current["ai_signal"] = True
        if current:
            entries.append(current)
        return entries
