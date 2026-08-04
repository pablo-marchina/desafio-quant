from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class EmbeddingCache:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._cache: dict[str, Any] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if ctx.chunk_id in self._cache:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        else:
            self._cache[ctx.chunk_id] = {"score": ctx.relevance_score, "content_len": len(ctx.content)}

        if len(self._cache) > 10000:
            keys = list(self._cache.keys())[:5000]

        for k in keys:
            del self._cache[k]

        return contexts
