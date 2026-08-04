from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RequestCoalescing:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._coalesce_map: dict[str, int] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            key = ctx.chunk_id[:30]

            self._coalesce_map[key] = self._coalesce_map.get(key, 0) + 1

            if self._coalesce_map[key] > 1:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
