"""Busca de URLs candidatas via Tavily (F1.1).

Primeiro estágio do pipeline de scraping (F1): dado um termo de busca, devolve
URLs candidatas (com título, trecho e score de relevância) para os adapters de
extração (Firecrawl/Playwright/trafilatura/BeautifulSoup, F1.2–F1.5) processarem.
Não coleta o conteúdo das páginas nem registra evidência — isso é F1.9; aqui é só
**descoberta**.

Usa o free tier do Tavily (`TAVILY_API_KEY`, F0.3). Este módulo é o adapter de busca
puro: o enviesamento da query e o pré-filtro por sinais AI-native ficam em `signals`
(F1.11, `bias_query`/`prefilter` sobre estes `SearchResult`); a guarda de quota por run
é F1.8. O client é importado de forma preguiçosa para que o parsing (`_parse`) seja
testável sem `tavily-python` instalado nem rede.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from packages.config import get_settings

SearchDepth = Literal["basic", "advanced"]


@dataclass(frozen=True)
class SearchResult:
    """Uma URL candidata devolvida pela busca, antes da extração (F1.2+).

    `score` é a relevância do Tavily (0–1). `snippet` é o trecho que o Tavily
    devolve (campo `content`), útil como pré-evidência até o fetch real (F1.9).
    """

    url: str
    title: str
    snippet: str
    score: float
    published_date: str | None = None


@lru_cache
def _client() -> Any:
    """`TavilyClient` cacheado (import preguiçoso). Requer `TAVILY_API_KEY`."""
    key = get_settings().tavily_api_key
    if not key:
        raise RuntimeError("TAVILY_API_KEY ausente — configure o .env para a busca (F1.1).")
    from tavily import TavilyClient

    return TavilyClient(api_key=key)


def _parse(payload: dict[str, Any]) -> tuple[SearchResult, ...]:
    """Converte a resposta crua do Tavily em `SearchResult` (puro, testável offline)."""
    results: list[SearchResult] = []
    for raw in payload.get("results", []):
        url = raw.get("url")
        if not url:
            continue
        results.append(
            SearchResult(
                url=url,
                title=raw.get("title", ""),
                snippet=raw.get("content", ""),
                score=float(raw.get("score", 0.0)),
                published_date=raw.get("published_date"),
            )
        )
    return tuple(results)


def search(
    query: str,
    *,
    max_results: int = 8,
    search_depth: SearchDepth = "basic",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> tuple[SearchResult, ...]:
    """Busca `query` no Tavily e devolve URLs candidatas ordenadas por relevância.

    `search_depth="basic"` é o default barato do free tier (F1.8); `"advanced"`
    custa mais créditos. `include_domains`/`exclude_domains` restringem o escopo
    (ex.: priorizar sites/blogs oficiais e notícias §9.2, F1.15).
    """
    if not query.strip():
        raise ValueError("query vazia")
    payload = _client().search(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        include_domains=include_domains or None,
        exclude_domains=exclude_domains or None,
    )
    return _parse(payload)
