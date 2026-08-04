from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


STARTUP_CARD_SELECTORS: dict[str, dict[str, str]] = {
    "distrito": {"card": "startup-card", "name": "h3", "link": "a"},
    "cubo": {"card": "member-card", "name": "name", "link": "a[href]"},
    "openstartups": {"card": "tr", "name": "td.name", "link": "a"},
    "startse": {"card": "startup-item", "name": "h2", "link": "a"},
    "ace": {"card": "company-card", "name": "h3", "link": "a"},
    "inovativa": {"card": "startup-card", "name": "h2", "link": "a"},
    "bossa": {"card": "venture-card", "name": "h3", "link": "a"},
}


def extract_startups(source_id: str, html: str, base_url: str = "") -> list[dict[str, str]]:
    """Extract startup names and URLs from a directory page HTML.

    Args:
        source_id: Directory source identifier.
        html: Raw HTML of the directory page.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with keys ``name`` and ``url``.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    selectors = STARTUP_CARD_SELECTORS.get(source_id, {})

    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    if selectors.get("card"):
        cards = soup.find_all(class_=selectors["card"])
        for card in cards:
            name_el = card.find(selectors["name"]) if selectors.get("name") else card
            link_el = card.find("a", href=True) if not selectors.get("link") else card.select_one(selectors["link"])
            name = name_el.get_text(strip=True) if name_el else ""
            href = link_el.get("href", "") if link_el else ""
            if href and not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(base_url.rstrip("/") + "/", href.lstrip("/"))
            if name and href and href not in seen_urls:
                seen_urls.add(href)
                entries.append({"name": name, "url": href})
    else:
        generic_links = soup.find_all("a", href=re.compile(r"/(startup|company|venture|organizac)", re.IGNORECASE))
        for link in generic_links:
            href = link.get("href", "")
            name = link.get_text(strip=True)
            if name and href:
                if not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(base_url.rstrip("/") + "/", href.lstrip("/"))
                if href not in seen_urls:
                    seen_urls.add(href)
                    entries.append({"name": name, "url": href})

    return entries
