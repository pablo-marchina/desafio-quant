from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """A single search result from any engine."""

    url: str
    title: str
    snippet: str
    source_engine: str
    rank: int = 0


@dataclass
class SearchResponse:
    """Aggregated search results with metadata."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    engine_counts: dict[str, int] = field(default_factory=dict)


class SearchEngine(ABC):
    """Abstract interface for a search engine adapter."""

    @abstractmethod
    def search(self, query: str, count: int = 10) -> list[SearchResult]:
        ...


class DuckDuckGoEngine(SearchEngine):
    """Search via DuckDuckGo (free, no API key required)."""

    def search(self, query: str, count: int = 10) -> list[SearchResult]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=count))
        except Exception as exc:
            logger.warning("DuckDuckGo search failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for i, r in enumerate(raw):
            url = r.get("href", "") or r.get("link", "")
            if url:
                results.append(
                    SearchResult(
                        url=url,
                        title=r.get("title", "") or "",
                        snippet=r.get("body", "") or "",
                        source_engine="duckduckgo",
                        rank=i + 1,
                    )
                )
        return results


class SerpApiEngine(SearchEngine):
    """Search via SerpAPI (requires SERPAPI_API_KEY env var, free tier 100/mo)."""

    def search(self, query: str, count: int = 10) -> list[SearchResult]:
        import os

        api_key = os.environ.get("SERPAPI_API_KEY", "")
        if not api_key:
            logger.warning("SERPAPI_API_KEY not set — skipping SerpAPI search")
            return []

        try:
            from serpapi import GoogleSearch

            params = {"q": query, "api_key": api_key, "num": count, "hl": "pt-br"}
            raw = GoogleSearch(params).get_dict()
            organic = raw.get("organic_results", [])
        except Exception as exc:
            logger.warning("SerpAPI search failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for i, r in enumerate(organic):
            url = r.get("link", "")
            if url:
                results.append(
                    SearchResult(
                        url=url,
                        title=r.get("title", "") or "",
                        snippet=r.get("snippet", "") or "",
                        source_engine="serpapi",
                        rank=i + 1,
                    )
                )
        return results


class GoogleCseEngine(SearchEngine):
    """Search via Google Custom Search (requires GOOGLE_CSE_API_KEY + CX, free 100 queries/day)."""

    def search(self, query: str, count: int = 10) -> list[SearchResult]:
        import os

        api_key = os.environ.get("GOOGLE_CSE_API_KEY", "")
        cx = os.environ.get("GOOGLE_CSE_CX", "")
        if not api_key or not cx:
            logger.warning("GOOGLE_CSE_API_KEY or GOOGLE_CSE_CX not set — skipping Google CSE")
            return []

        try:
            import httpx

            resp = httpx.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": api_key, "cx": cx, "q": query, "num": min(count, 10)},
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json()
            items = raw.get("items", [])
        except Exception as exc:
            logger.warning("Google CSE search failed: %s", exc)
            return []

        results: list[SearchResult] = []
        for i, item in enumerate(items):
            url = item.get("link", "")
            if url:
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", "") or "",
                        snippet=item.get("snippet", "") or "",
                        source_engine="google_cse",
                        rank=i + 1,
                    )
                )
        return results


class SearchAggregator:
    """Aggregate results from multiple search engines with dedup."""

    def __init__(self, engines: list[SearchEngine] | None = None):
        self._engines: list[SearchEngine] = engines or [
            DuckDuckGoEngine(),
        ]

    def add_engine(self, engine: SearchEngine) -> None:
        self._engines.append(engine)

    def search(self, query: str, max_results: int = 20) -> SearchResponse:
        """Query all engines, dedup by URL, return ranked results."""
        response = SearchResponse(query=query)

        all_results: list[SearchResult] = []
        for engine in self._engines:
            try:
                engine_results = engine.search(query, count=max_results)
                all_results.extend(engine_results)
            except Exception as exc:
                logger.warning("Engine %s failed: %s", type(engine).__name__, exc)

        # Dedup by URL (keep first occurrence, which is from highest-priority engine)
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in all_results:
            key = sha256(r.url.encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        # Re-rank
        for i, r in enumerate(deduped):
            r.rank = i + 1

        response.results = deduped[:max_results]
        response.engine_counts = _count_engines(all_results)
        return response


def _count_engines(results: list[SearchResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.source_engine] = counts.get(r.source_engine, 0) + 1
    return counts
