"""Conector D - Astella Investment (portfolio de VC early-stage).

Dados renderizados no HTML dentro de div.split-portfolios (BeautifulSoup).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import StartupRecord
from .base import BaseConnector

ASTELLA_URL = "https://www.astella.com.br/pt/portfolio"

# --- Seletores isolados (ajustar aqui se a marcacao do site mudar) ---
CONTAINER_SELECTOR = "div.split-portfolios"
# Cada marca costuma ser um link/card filho; cobrimos algumas variacoes.
ITEM_SELECTORS = ("a", "[class*='portfolio-item']", "[class*='brand']", "li")


class AstellaConnector(BaseConnector):
    source_name = "Astella"

    async def fetch(self) -> list[StartupRecord]:
        html = await self.fetcher.get_text(ASTELLA_URL)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one(CONTAINER_SELECTOR)
        if container is None:
            self.log.warning("Container '%s' nao encontrado.", CONTAINER_SELECTOR)
            container = soup

        items = []
        for sel in ITEM_SELECTORS:
            items = container.select(sel)
            if items:
                break

        records: list[StartupRecord] = []
        seen: set[str] = set()
        for el in items:
            try:
                name = (
                    el.get("title")
                    or el.get("data-name")
                    or el.get_text(strip=True)
                )
                if not name:
                    img = el.find("img")
                    name = img.get("alt") if img else None
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                href = el.get("href") if el.name == "a" else None
                if not href:
                    link = el.find("a")
                    href = link.get("href") if link else None
                records.append(
                    StartupRecord(
                        name=name,
                        sector="Portfolio VC",
                        official_website=href,
                        source_name=self.source_name,
                        source_url=ASTELLA_URL,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self.log.debug("Item ignorado na Astella: %s", exc)
        return records
