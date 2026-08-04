"""Adapter Tavily para busca web durante enriquecimento de candidatos."""

import httpx

from apps.api.src.modules.startup_discovery.application.ports import (
    WebSearchPort,
    WebSearchResult,
)
from apps.api.src.shared.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = 15.0


class TavilyWebSearchAdapter(WebSearchPort):
    """Chama a API Tavily para busca web, retorna lista de WebSearchResult.

    Degradacao graciosa: excecoes de rede ou HTTP sao capturadas e devolvem
    lista vazia, permitindo que o enriquecimento continue sem a chave ou
    quando a API esta indisponivel.
    """

    def __init__(self, api_key: str, search_url: str) -> None:
        self._api_key = api_key
        self._search_url = search_url

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        if not self._api_key:
            return []

        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(self._search_url, json=payload)
                response.raise_for_status()
            data = response.json()
            return [
                WebSearchResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    snippet=r.get("content", ""),
                )
                for r in data.get("results", [])
                if r.get("url")
            ]
        except Exception as exc:
            logger.warning(
                "tavily search failed, returning empty results",
                extra={"query": query[:80], "reason": str(exc)},
            )
            return []
