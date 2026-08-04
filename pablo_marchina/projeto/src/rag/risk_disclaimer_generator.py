"""risk disclaimer generator

Hypothesis: Evaluate whether risk disclaimer generator improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RiskDisclaimerGenerator:
    """risk disclaimer generator"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        risk_triggers = [
            "risk",
            "uncertain",
            "may",
            "could",
            "possible",
            "potential",
            "estimate",
            "projected",
            "approximate",
        ]

        for ctx in contexts:
            risk_count = sum(1 for r in risk_triggers if r.lower() in ctx.content.lower())

            if risk_count >= 3:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
