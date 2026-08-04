"""retrieval depth adequacy

Hypothesis: Evaluate whether retrieval depth adequacy improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrievalDepthAdequacy:
    """retrieval depth adequacy"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        depth = kwargs.get("depth", 1)
        max_depth = self.config.get("max_depth", 5)

        adequacy = 1.0 - abs(depth - max_depth) / max_depth

        for ctx in contexts:
            ctx.relevance_score = min(1.0, ctx.relevance_score * 0.4 + adequacy * 0.6)

        return contexts
