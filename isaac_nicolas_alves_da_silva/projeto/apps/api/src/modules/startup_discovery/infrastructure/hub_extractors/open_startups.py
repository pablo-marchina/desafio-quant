"""Extrator de nomes de startups do 100 Open Startups (modo name).

O ranking do 100 Open Startups e carregado via JavaScript:
  https://www.openstartups.net/site/ranking/data/rankings/categories/2025.js

O arquivo contem uma variavel JS:
  var topCategories2025 = [ { "category": "TOP 10 Artificial Intelligence 2025",
                               "startups": [{"name": "Noleak", "rank": 1}, ...] },
                             ... ];

Estrategia:
  1. Faz GET do arquivo JS (texto puro, sem renderizacao).
  2. Remove o prefixo "var topCategories2025 = " e o sufixo ";".
  3. Parse JSON.
  4. Filtra categorias configuradas em OPEN_STARTUPS_CATEGORIES.
  5. Retorna lista de DiscoveredCandidateItem (nome + categoria + rank).

Sem fallback HTML — se o JS mudar de URL ou formato, o extrator falha
explicitamente para que o problema seja identificado rapidamente.

Ajuste OPEN_STARTUPS_JS_URL se o arquivo mudar de nome (ex: 2026.js).
"""

import json
import re

import httpx

from apps.api.src.modules.startup_discovery.application.dto import DiscoveredCandidateItem
from apps.api.src.modules.startup_discovery.application.ports import HubNameExtractor
from apps.api.src.modules.startup_discovery.domain.hub_registry import (
    OPEN_STARTUPS_CATEGORIES,
)
from apps.api.src.shared.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = 20.0
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NvidiaStartupRadar/1.0; +https://radar.example.com)"
    ),
    "Accept": "application/javascript, text/plain, */*",
}
_JS_VAR_RE = re.compile(r"^\s*var\s+\w+\s*=\s*", re.MULTILINE)


class OpenStartupsExtractor(HubNameExtractor):
    """Extrai nomes de startups do arquivo JS de categorias do 100 Open Startups."""

    async def extract(
        self,
        listing_url: str,
        *,
        limit: int,
    ) -> list[DiscoveredCandidateItem]:
        raw = await self._fetch_js(listing_url)
        categories = self._parse_js(raw)
        return self._select_candidates(categories, listing_url, limit)

    async def _fetch_js(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.text

    def _parse_js(self, raw: str) -> list[dict]:
        """Remove prefixo de variavel JS, parseia o JSON e retorna a lista de categorias.

        O arquivo tem estrutura aninhada:
          [{"name": "Ranking 100 Open Startups", "children": [<categorias>]}]
        Retorna diretamente a lista de categorias (children do primeiro elemento).
        """
        text = _JS_VAR_RE.sub("", raw).strip().rstrip(";").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Falha ao parsear JSON do arquivo JS do Open Startups: {exc}"
            ) from exc
        if not isinstance(data, list) or not data:
            raise ValueError(
                f"Esperava lista nao-vazia no JSON do Open Startups, recebi {type(data).__name__}"
            )
        # Suporta tanto lista plana de categorias quanto wrapper com children
        first = data[0]
        if isinstance(first, dict) and "children" in first and "name" not in first.get("startups", [""]):
            categories = first.get("children", [])
        else:
            categories = data
        return categories

    def _select_candidates(
        self,
        categories: list[dict],
        source_url: str,
        limit: int,
    ) -> list[DiscoveredCandidateItem]:
        target_categories = {c.lower() for c in OPEN_STARTUPS_CATEGORIES}
        candidates: list[DiscoveredCandidateItem] = []
        seen_names: set[str] = set()

        for entry in categories:
            # Suporta tanto "category" (formato antigo) quanto "name" (formato atual)
            category = str(entry.get("name") or entry.get("category") or "")
            if category.lower() not in target_categories:
                continue

            # Suporta tanto "startups" (formato antigo) quanto "children" (formato atual)
            startups = entry.get("children") or entry.get("startups") or []
            if not isinstance(startups, list):
                continue

            for startup in startups:
                if len(candidates) >= limit:
                    return candidates

                name = str(startup.get("name", "")).strip()
                if not name or name.lower() in seen_names:
                    continue

                seen_names.add(name.lower())
                rank_raw = startup.get("rank") or startup.get("position")
                rank: int | None = None
                try:
                    rank = int(rank_raw) if rank_raw is not None else None
                except (TypeError, ValueError):
                    pass

                candidates.append(
                    DiscoveredCandidateItem(
                        name=name,
                        category=category,
                        rank=rank,
                        description=None,
                    )
                )

                logger.debug(
                    "open_startups candidate extracted",
                    extra={"name": name, "category": category, "rank": rank},
                )

        logger.info(
            "open_startups extraction completed",
            extra={"total": len(candidates), "source_url": source_url},
        )
        return candidates
