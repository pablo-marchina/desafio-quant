"""Conector B - 100 Open Startups (arrays JS estaticos, rankings 2020-2025).

Os arquivos de origem nao sao JSON puro: sao scripts JS que instanciam um array
de objetos. Baixamos como texto e isolamos o array via regex antes do json.loads.
Os anos sao varridos em paralelo.
"""
from __future__ import annotations

import asyncio
import json
import re

from ..models import StartupRecord
from .base import BaseConnector

YEARS = range(2020, 2026)  # 2020..2025
URL_TEMPLATE = (
    "https://www.openstartups.net/site/ranking/data/rankings/startups/{year}-all.js"
)

# --- Regex isoladas (fonte suscetivel a quebras; editar aqui se o layout mudar) ---
# Captura o array de objetos JS: [ { ... }, { ... } ]. Guloso ate o ultimo "}"
# seguido de virgula/espaco opcional e "]", para tolerar virgula pendente final.
REGEX_JS_ARRAY = re.compile(r"(\[\s*\{.*\}[\s,]*\])", re.DOTALL)
# Converte chaves nao-aspadas (ex.: name:) em chaves JSON validas ("name":).
REGEX_BARE_KEY = re.compile(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)")
# Remove virgulas penduradas antes de } ou ].
REGEX_TRAILING_COMMA = re.compile(r",(\s*[}\]])")

NAME_KEYS = ("name", "nome", "startup", "company", "title")
SECTOR_KEYS = ("sector", "setor", "segment", "category", "vertical", "industry")
WEBSITE_KEYS = ("website", "site", "url", "link", "homepage")


def _coerce_json(blob: str) -> list[dict]:
    """Normaliza um array de objetos JS para JSON parseavel."""
    text = REGEX_BARE_KEY.sub(r'\1"\2"\3', blob)
    text = text.replace("'", '"')
    text = REGEX_TRAILING_COMMA.sub(r"\1", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [x for x in data if isinstance(x, dict)]


def _first(d: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        val = d.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


class OpenStartupsConnector(BaseConnector):
    source_name = "100 Open Startups"

    async def _fetch_year(self, year: int) -> list[StartupRecord]:
        url = URL_TEMPLATE.format(year=year)
        raw = await self.fetcher.get_text(url)
        if not raw:
            return []
        match = REGEX_JS_ARRAY.search(raw)
        if not match:
            self.log.warning("Array JS nao localizado no ranking de %d.", year)
            return []
        source_label = f"{self.source_name} ({year})"
        records: list[StartupRecord] = []
        for item in _coerce_json(match.group(1)):
            try:
                name = _first(item, NAME_KEYS)
                if not name:
                    continue
                records.append(
                    StartupRecord(
                        name=name,
                        sector=_first(item, SECTOR_KEYS),
                        official_website=_first(item, WEBSITE_KEYS),
                        source_name=source_label,
                        source_url=url,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self.log.debug("Item ignorado em %d: %s", year, exc)
        self.log.info("Ano %d: %d startups.", year, len(records))
        return records

    async def fetch(self) -> list[StartupRecord]:
        results = await asyncio.gather(
            *(self._fetch_year(y) for y in YEARS), return_exceptions=True
        )
        records: list[StartupRecord] = []
        for res in results:
            if isinstance(res, Exception):
                self.log.warning("Falha em um dos anos: %s", res)
                continue
            records.extend(res)
        return records
