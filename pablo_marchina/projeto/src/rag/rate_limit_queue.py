from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RateLimitQueue:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._queue: list[float] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import time

        now = time.time()
        self._queue.append(now)
        cutoff = now - 60.0
        self._queue = [t for t in self._queue if t > cutoff]
        depth = len(self._queue)
        for ctx in contexts:
            if depth > 50:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        else:
            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
