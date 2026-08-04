"""explicit degradation report

Hypothesis: Evaluate whether explicit degradation report improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ExplicitDegradationReport:
    """explicit degradation report"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_baseline_avg", None):
            avg_scores = [c.relevance_score for c in contexts]

            self._baseline_avg = sum(avg_scores) / max(len(avg_scores), 1) if avg_scores else 0.0

        current_avg = sum(c.relevance_score for c in contexts) / max(len(contexts), 1)

        degradation = current_avg < self._baseline_avg * 0.8

        for ctx in contexts:
            if degradation:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
