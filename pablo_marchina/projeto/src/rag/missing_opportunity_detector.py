"""missing opportunity detector

Hypothesis: Evaluate whether missing opportunity detector improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MissingOpportunityDetector:
    """missing opportunity detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        opp_keywords = [
            "opportunity",
            "potential",
            "advantage",
            "benefit",
            "growth",
            "improvement",
            "innovation",
            "breakthrough",
        ]

        for ctx in contexts:
            opp_count = sum(1 for o in opp_keywords if o.lower() in ctx.content.lower())

            if opp_count < 2:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

            else:
                ctx.relevance_score = min(1.0, ctx.relevance_score + opp_count * 0.02)

        return contexts
