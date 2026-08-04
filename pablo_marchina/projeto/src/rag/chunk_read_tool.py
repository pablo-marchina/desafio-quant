"""chunk read tool

Hypothesis: Evaluate whether chunk read tool improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ChunkReadTool:
    """chunk read tool"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_chunk_log", None):
            self._chunk_log: list[str] = []

        for ctx in contexts:
            self._chunk_log.append(ctx.chunk_id)

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.01)

        self._chunk_log = self._chunk_log[-200:]

        return contexts
