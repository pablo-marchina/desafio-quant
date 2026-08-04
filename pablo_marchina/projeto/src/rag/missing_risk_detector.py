"""missing risk detector

Hypothesis: Evaluate whether missing risk detector improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MissingRiskDetector:
    """missing risk detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        risk_keywords = [
            "risk",
            "threat",
            "vulnerability",
            "concern",
            "downside",
            "drawback",
            "limitation",
            "challenge",
        ]

        for ctx in contexts:
            risk_count = sum(1 for r in risk_keywords if r.lower() in ctx.content.lower())

            if risk_count < 2:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

            else:
                ctx.relevance_score = min(1.0, ctx.relevance_score + risk_count * 0.02)

        return contexts
