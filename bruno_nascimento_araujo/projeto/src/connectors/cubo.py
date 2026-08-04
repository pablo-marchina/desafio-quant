"""Conector A - Cubo Itau (API JSON one-shot).

Estrategia: uma unica requisicao com limit alto coleta toda a base, evitando
paginacao redundante.
"""
from __future__ import annotations

from ..models import StartupRecord
from .base import BaseConnector

# Endpoint obtido via engenharia reversa; centralizado para ajuste rapido.
CUBO_URL = "https://api.site.cubo.itau/startups?limit=511&page=1"

# Possiveis nomes de campo no payload (a API pode variar). Tentamos em ordem.
NAME_KEYS = ("name", "nome", "title", "companyName")
SECTOR_KEYS = ("segment", "category", "sector", "segmento", "categoria", "industry")
WEBSITE_KEYS = ("website", "site", "url", "siteUrl", "homepage")


def _first(d: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        val = d.get(k)
        if isinstance(val, dict):  # ex.: {"name": "..."} aninhado
            val = val.get("name") or val.get("title")
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _iter_items(payload) -> list[dict]:
    """Localiza a lista de startups dentro de formatos comuns de resposta."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "startups", "content"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


class CuboConnector(BaseConnector):
    source_name = "Cubo"

    async def fetch(self) -> list[StartupRecord]:
        payload = await self.fetcher.get_json(CUBO_URL)
        if payload is None:
            self.log.warning("Sem resposta da API do Cubo.")
            return []
        items = _iter_items(payload)
        records: list[StartupRecord] = []
        for item in items:
            try:
                name = _first(item, NAME_KEYS)
                if not name:
                    continue
                records.append(
                    StartupRecord(
                        name=name,
                        sector=_first(item, SECTOR_KEYS),
                        official_website=_first(item, WEBSITE_KEYS),
                        source_name=self.source_name,
                        source_url=CUBO_URL,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self.log.debug("Item ignorado no Cubo: %s", exc)
        return records
