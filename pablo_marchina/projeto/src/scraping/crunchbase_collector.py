from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _product_mode_disabled() -> bool:
    import os
    return os.getenv("APP_MODE", "").casefold() == "product"


@dataclass
class CrunchbaseProfile:
    name: str
    description: str = ""
    website: str = ""
    founded_year: int | None = None
    founders: list[str] = field(default_factory=list)
    funding_stage: str = ""
    total_funding_usd: float | None = None
    investors: list[str] = field(default_factory=list)
    source_url: str = ""


class CrunchbaseCollector:
    """Basic Crunchbase company data via public pages.

    Uses web scraping of public Crunchbase pages. No API key needed
    for basic public profile access.
    """

    BASE_URL = "https://www.crunchbase.com"

    def collect_company(self, company_name: str) -> CrunchbaseProfile | None:
        """Search Crunchbase for *company_name*, collect public profile data."""
        slug = self._search_slug(company_name)
        if slug is None:
            logger.info("Crunchbase slug not found for '%s'", company_name)
            return None
        return self._collect_by_slug(slug)

    def _search_slug(self, company_name: str) -> str | None:
        if _product_mode_disabled():
            raise RuntimeError("Crunchbase direct collector is disabled in APP_MODE=product; use governed source registry.")
        search_url = f"{self.BASE_URL}/search/organization.companies"
        try:
            resp = httpx.get(
                search_url,
                params={"query": company_name, "limit": 3},
                timeout=15,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return None
            import re
            pattern = re.compile(
                r'/organization/([a-z0-9-]+)',
                re.IGNORECASE,
            )
            slugs = pattern.findall(resp.text)
            return slugs[0] if slugs else None
        except Exception as exc:
            logger.warning("Crunchbase search failed for '%s': %s", company_name, exc)
            return None

    def _collect_by_slug(self, slug: str) -> CrunchbaseProfile | None:
        profile_url = f"{self.BASE_URL}/organization/{slug}"
        try:
            resp = httpx.get(profile_url, timeout=20, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return None

            import re
            html = resp.text

            name = self._extract_meta(html, "og:title") or slug.replace("-", " ").title()
            description = self._extract_meta(html, "og:description") or ""
            website = self._extract_meta(html, "og:url") or ""

            founder_names: list[str] = []
            founder_pattern = re.compile(
                r'"full_name"\s*:\s*"([^"]+)"',
                re.IGNORECASE,
            )
            for match in founder_pattern.finditer(html):
                fn = match.group(1).strip()
                if fn and fn not in founder_names:
                    founder_names.append(fn)

            funding_pattern = re.compile(
                r'"money_raised"(?:\s*:\s*)(\d+(?:\.\d+)?)',
                re.IGNORECASE,
            )
            funding_match = funding_pattern.search(html)

            return CrunchbaseProfile(
                name=name,
                description=description[:500],
                website=website,
                founders=founder_names[:10],
                source_url=profile_url,
                total_funding_usd=float(funding_match.group(1)) if funding_match else None,
            )
        except Exception as exc:
            logger.warning("Crunchbase profile fetch failed for '%s': %s", slug, exc)
            return None

    @staticmethod
    def _extract_meta(html: str, property_name: str) -> str:
        import re
        pattern = re.compile(
            rf'<meta\s+[^>]*property=["\']{property_name}["\']\s+content=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        match = pattern.search(html)
        return match.group(1) if match else ""
