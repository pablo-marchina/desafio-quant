"""review status

Hypothesis: Evaluate whether review status improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReviewStatus:
    """review status"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            reviewed = any(w in ctx.content.lower() for w in ["reviewed", "approved", "signed off"])

            if reviewed:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.08)

            else:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
