"""Executor de busca web usando a API HTTP do Tavily."""

from collections.abc import Callable
from urllib.parse import urlparse, urlunparse

import httpx

from apps.api.src.modules.agents.application.dto import (
    SearchExecutionResult,
    SearchResultCandidate,
)
from apps.api.src.modules.agents.application.ports import SearchExecutorPort
from apps.api.src.modules.agents.domain.exceptions import AgentSearchExecutionError

TAVILY_TIMEOUT_SECONDS = 30

TavilyClientFactory = Callable[[], httpx.AsyncClient]


def _normalize_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))


class TavilySearchExecutor(SearchExecutorPort):
    """Transforma queries do Search Planner em URLs reais via Tavily."""

    def __init__(
        self,
        *,
        api_key: str,
        search_url: str,
        client_factory: TavilyClientFactory | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("TAVILY_API_KEY e obrigatoria.")
        if not search_url:
            raise ValueError("TAVILY_SEARCH_URL e obrigatoria.")

        self._api_key = api_key
        self._search_url = search_url
        self._client_factory = client_factory or self._create_default_client

    def _create_default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=TAVILY_TIMEOUT_SECONDS)

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        excluded_urls: list[str] | None = None,
    ) -> SearchExecutionResult:
        clean_query = query.strip()
        if not clean_query:
            return SearchExecutionResult(query=query, results=[])

        payload = {
            "api_key": self._api_key,
            "query": clean_query,
            "search_depth": "basic",
            "max_results": max(1, min(max_results, 10)),
            "include_answer": False,
            "include_raw_content": False,
        }

        try:
            async with self._client_factory() as client:
                response = await client.post(self._search_url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as error:
            raise AgentSearchExecutionError("Busca Tavily excedeu o tempo limite.") from error
        except httpx.HTTPError as error:
            raise AgentSearchExecutionError(f"Busca Tavily falhou: {error}.") from error
        except ValueError as error:
            raise AgentSearchExecutionError(
                "Tavily devolveu uma resposta que nao e JSON valido."
            ) from error

        raw_results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(raw_results, list):
            raise AgentSearchExecutionError(
                "Tavily devolveu uma resposta sem lista de resultados."
            )

        excluded = {
            normalized
            for url in (excluded_urls or [])
            if (normalized := _normalize_url(url)) is not None
        }
        seen: set[str] = set()
        results: list[SearchResultCandidate] = []

        for item in raw_results:
            if not isinstance(item, dict):
                continue
            normalized_url = _normalize_url(str(item.get("url", "")))
            if (
                normalized_url is None
                or normalized_url in excluded
                or normalized_url in seen
            ):
                continue
            seen.add(normalized_url)
            results.append(
                SearchResultCandidate(
                    url=normalized_url,
                    title=str(item["title"]).strip() if item.get("title") else None,
                    snippet=str(item["content"]).strip()
                    if item.get("content")
                    else None,
                    score=float(item["score"])
                    if isinstance(item.get("score"), int | float)
                    else None,
                )
            )

        return SearchExecutionResult(query=clean_query, results=results)
