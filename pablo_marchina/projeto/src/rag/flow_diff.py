from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FlowDiff:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._prev_flow_ids: set[str] = set()

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        current_ids = {ctx.chunk_id for ctx in contexts}
        added = current_ids - self._prev_flow_ids if self._prev_flow_ids else set()
        removed = self._prev_flow_ids - current_ids if self._prev_flow_ids else set()
        for ctx in contexts:
            if ctx.chunk_id in added:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

                if ctx.chunk_id in removed:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

                    self._prev_flow_ids = current_ids
        return contexts
