from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PriorityQueueByExpectedUtility:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._queue: list[tuple[float, str]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            utility = ctx.relevance_score * len(ctx.content.split())

            self._queue.append((utility, ctx.chunk_id))

            self._queue.sort(reverse=True)
            self._queue = self._queue[:200]
            ranked_ids = {cid: i for i, (_, cid) in enumerate(self._queue)}
            for ctx in contexts:
                rank = ranked_ids.get(ctx.chunk_id)

                if rank is not None:
                    boost = max(0, 50 - rank) * 0.003

                    ctx.relevance_score = min(1.0, ctx.relevance_score + boost)

        return contexts
