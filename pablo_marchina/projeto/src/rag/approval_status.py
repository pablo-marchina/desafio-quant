"""approval status

Hypothesis: Evaluate whether approval status improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ApprovalStatus:
    """approval status"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            approved_terms = ["approved", "accepted", "authorized", "validated"]

            rejected_terms = ["rejected", "denied", "revoked", "invalidated"]

            if any(t in ctx.content.lower() for t in approved_terms):
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

            if any(t in ctx.content.lower() for t in rejected_terms):
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

        return contexts
