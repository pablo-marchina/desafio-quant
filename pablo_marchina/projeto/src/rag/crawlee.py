from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Crawlee:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._queue: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            priority = ctx.relevance_score * len(ctx.content)

            self._queue.append(
                {"url": ctx.url, "source_id": ctx.source_id, "priority": priority, "score": ctx.relevance_score}
            )

            self._queue.sort(key=lambda x: x["priority"], reverse=True)
            self._queue = self._queue[:500]
        return contexts
