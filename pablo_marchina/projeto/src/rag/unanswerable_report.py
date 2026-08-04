"""unanswerable report

Hypothesis: Evaluate whether unanswerable report improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class UnanswerableReport:
    """unanswerable report"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        threshold = self.config.get("answerability_threshold", 0.3)
        answerable = sum(1 for c in contexts if c.relevance_score >= threshold)

        if answerable < 1:
            return []

        return contexts
