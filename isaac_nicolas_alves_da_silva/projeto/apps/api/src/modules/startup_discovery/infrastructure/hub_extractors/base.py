"""Implementacao base compartilhada pelos extratores de links de hubs."""

from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from apps.api.src.modules.startup_discovery.application.dto import StartupCandidate
from apps.api.src.modules.startup_discovery.application.ports import (
    HubLinkExtractor,
)

FETCH_TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NvidiaStartupRadar/1.0; +https://radar.example.com)"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


class BaseHubLinkExtractor(HubLinkExtractor):
    """Classe base com utilitarios de fetch/normalizacao para extratores concretos."""

    async def _fetch(self, url: str) -> BeautifulSoup:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _is_external(self, href: str, hub_domain: str) -> bool:
        return (
            href.startswith("http")
            and hub_domain not in href
            and not href.startswith("#")
        )

    def _normalize(self, urls: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for url in urls:
            url = url.rstrip("/")
            if url not in seen:
                seen.add(url)
                result.append(url)
        return result

    def _normalize_candidates(
        self,
        candidates: list[StartupCandidate],
    ) -> list[StartupCandidate]:
        seen: set[str] = set()
        result: list[StartupCandidate] = []
        for candidate in candidates:
            website_url = candidate.website_url.strip().rstrip("/")
            if not website_url.startswith("http"):
                continue

            key = website_url.lower()
            if key in seen:
                continue

            seen.add(key)
            result.append(
                StartupCandidate(
                    website_url=website_url,
                    name=candidate.name,
                    hub_profile_url=candidate.hub_profile_url,
                    short_description=candidate.short_description,
                    declared_sector=candidate.declared_sector,
                )
            )
        return result

    def _clean_text(self, value: str | None, *, max_length: int = 180) -> str | None:
        if not value:
            return None
        clean = " ".join(value.split()).strip()
        if not clean or clean.startswith("http"):
            return None
        if len(clean) > max_length:
            return f"{clean[: max_length - 3].rstrip()}..."
        return clean

    def _absolute_url(self, href: str, base_url: str) -> str:
        return urljoin(base_url, href)

    def _candidate_from_external_anchor(
        self,
        tag,
        *,
        hub_domain: str,
    ) -> StartupCandidate | None:
        href = str(tag.get("href", "")).strip()
        if not self._is_external(href, hub_domain):
            return None
        return StartupCandidate(
            website_url=href,
            name=self._clean_text(tag.get_text(" ", strip=True)),
        )

    def _description_from_detail(self, soup: BeautifulSoup) -> str | None:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta is not None:
            description = self._clean_text(str(meta.get("content", "")), max_length=280)
            if description:
                return description

        paragraph = soup.find("p")
        if paragraph is not None:
            return self._clean_text(paragraph.get_text(" ", strip=True), max_length=280)

        return None
