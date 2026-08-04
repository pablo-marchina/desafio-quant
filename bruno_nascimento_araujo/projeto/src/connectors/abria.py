"""Conector C - ABRIA (Associacao Brasileira de Inteligencia Artificial).

Alta densidade de alvos AI-Native: por ser associacao de IA, marcamos os associados
diretamente como high_priority. Dados renderizados no HTML (BeautifulSoup).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from ..models import STATUS_HIGH, StartupRecord
from .base import BaseConnector

ABRIA_URL = "https://abria.org.br/associados/"

# --- Seletores isolados (ajustar aqui se a marcacao do site mudar) ---
CONTAINER_SELECTOR = "div.associados"
CARD_SELECTOR = "a.associado-card"
# Fallbacks caso a estrutura primaria nao seja encontrada.
CARD_FALLBACK_SELECTORS = ("a.associado-card", "a[class*='associado']", ".associados a")


class AbriaConnector(BaseConnector):
    source_name = "ABRIA"

    async def fetch(self) -> list[StartupRecord]:
        html = await self.fetcher.get_text(ABRIA_URL)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one(CONTAINER_SELECTOR) or soup
        cards = container.select(CARD_SELECTOR)
        if not cards:
            for sel in CARD_FALLBACK_SELECTORS:
                cards = container.select(sel)
                if cards:
                    self.log.info("Usando seletor fallback '%s'.", sel)
                    break

        records: list[StartupRecord] = []
        for card in cards:
            try:
                name = card.get("title") or card.get_text(strip=True)
                # Algumas marcacoes guardam o nome em <img alt="..."> dentro do card.
                if not name:
                    img = card.find("img")
                    name = img.get("alt") if img else None
                if not name:
                    continue
                href = card.get("href")
                records.append(
                    StartupRecord(
                        name=name,
                        sector="Inteligencia Artificial",
                        official_website=href,
                        source_name=self.source_name,
                        source_url=ABRIA_URL,
                        status=STATUS_HIGH,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self.log.debug("Card ignorado na ABRIA: %s", exc)
        return records
