from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrievalResultCache:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._cache: dict[str, Any] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "__no_query__")
        cache_key = query
        if cache_key in self._cache:
            cached_ids = set(self._cache[cache_key])

            for ctx in contexts:
                if ctx.chunk_id in cached_ids:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

                else:
                    self._cache[cache_key] = [ctx.chunk_id for ctx in contexts]

        return contexts
