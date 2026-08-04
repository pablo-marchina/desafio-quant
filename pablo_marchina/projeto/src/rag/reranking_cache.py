from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RerankingCache:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._cache: dict[str, Any] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        for ctx in contexts:
            cache_key = f"{query}:{ctx.chunk_id}"

        if cache_key in self._cache:
            ctx.relevance_score = self._cache[cache_key]

        else:
            self._cache[cache_key] = ctx.relevance_score

        return contexts
