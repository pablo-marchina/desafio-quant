"""implementation priority tier

Hypothesis: Evaluate whether implementation priority tier improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ImplementationPriorityTier:
    """implementation priority tier"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        priority_tiers = {
            "p0": 0.9,
            "p1": 0.7,
            "p2": 0.5,
            "p3": 0.3,
            "critical": 0.9,
            "high": 0.7,
            "medium": 0.5,
            "low": 0.3,
        }

        for ctx in contexts:
            text_lower = ctx.content.lower()

            for label, score in priority_tiers.items():
                if label in text_lower:
                    ctx.relevance_score = min(1.0, ctx.relevance_score * 0.5 + score * 0.5)

                    break

        return contexts
