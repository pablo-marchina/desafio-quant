"""implementation readiness review

Hypothesis: Evaluate whether implementation readiness review improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ImplementationReadinessReview:
    """implementation readiness review"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        readiness_terms = {
            "ready",
            "completed",
            "verified",
            "tested",
            "approved",
            "deployed",
            "validated",
            "signed off",
        }

        blockers = {"blocked", "waiting", "pending", "draft", "in progress", "not started"}

        for ctx in contexts:
            ready_count = sum(1 for r in readiness_terms if r.lower() in ctx.content.lower())

            block_count = sum(1 for b in blockers if b.lower() in ctx.content.lower())

            readiness_score = (ready_count - block_count) * 0.05

            ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score + readiness_score))

        return contexts
