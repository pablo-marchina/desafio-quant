from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class LlmResponseCache:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._cache: dict[str, Any] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            cache_key = ctx.content[:200]

        if cache_key in self._cache:
            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.03)

        else:
            self._cache[cache_key] = {"chunk_id": ctx.chunk_id, "score": ctx.relevance_score}

        return contexts
