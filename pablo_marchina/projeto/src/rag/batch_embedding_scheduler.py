from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class BatchEmbeddingScheduler:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._batch_count: int = 0

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        batch_size = self.config.get("batch_size", 32)
        for ctx in contexts:
            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.01)

            self._batch_count += (len(contexts) + batch_size - 1) // batch_size
        return contexts
