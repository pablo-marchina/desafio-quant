"""trade-off matrix

Hypothesis: Evaluate whether trade-off matrix improves final product output without paid dependency.
Category: 8.46 Decision Accountability and Responsibility
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class TradeOffMatrix:
    """trade-off matrix — evaluate contexts across multiple decision criteria."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            criteria_weights = {
                "relevance": kwargs.get("relevance_weight", 0.3),
                "freshness": kwargs.get("freshness_weight", 0.2),
                "authority": kwargs.get("authority_weight", 0.2),
                "coverage": kwargs.get("coverage_weight", 0.15),
                "diversity": kwargs.get("diversity_weight", 0.15),
            }
            source_ids = set()
            for ctx in contexts:
                source_ids.add(ctx.source_id)

                diversity_score = len(source_ids) / max(len(contexts), 1)
                for ctx in contexts:
                    tradeoff_score = 0.0

                    tradeoff_score += ctx.relevance_score * criteria_weights["relevance"]

                    tradeoff_score += (0.1 if ctx.url else 0.0) * criteria_weights["freshness"]

                    url_lower = (ctx.url or "").lower()

                    authority = 0.15 if ctx.url and any(d in url_lower for d in [".gov", ".edu", "nvidia.com"]) else 0.0

                    tradeoff_score += authority * criteria_weights["authority"]

                    gap_coverage = len(ctx.gap_types) * 0.05

                    tradeoff_score += gap_coverage * criteria_weights["coverage"]

                    tradeoff_score += diversity_score * criteria_weights["diversity"]

                    ctx.relevance_score = min(1.0, max(0.0, tradeoff_score))

        return contexts
