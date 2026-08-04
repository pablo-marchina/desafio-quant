from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from src.discovery.source_registry import DiscoverySource
from src.scraping.scrapers.base_scraper import SourceScraper


class OpenStartupsScraper(SourceScraper):
    source_id = "open_startups_ecosystem"
    name = "100 Open Startups — Ranking"
    allowed_domains = ["100openstartups.com"]

    def extract_entries(self, html: str, source: DiscoverySource) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if not re.search(r"/startups?/", href, re.IGNORECASE):
                continue
            name = (a_tag.get_text(strip=True) or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            description = ""
            parent = a_tag.parent
            if parent:
                text_parts = [t.strip() for t in parent.stripped_strings if t.strip() and t.strip() != name]
                if text_parts:
                    description = text_parts[0][:200]
            entries.append({
                "name": name,
                "description": description,
                "url": href if href.startswith("http") else f"https://100openstartups.com{href}",
            })
        return entries
