"""output improvement gate

Hypothesis: Evaluate whether output improvement gate improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class OutputImprovementGate:
    """output improvement gate"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        threshold = self.config.get("quality_threshold", 0.5)
        avg_score = sum(c.relevance_score for c in contexts) / max(len(contexts), 1)

        needs_improvement = avg_score < threshold

        for ctx in contexts:
            if needs_improvement:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
