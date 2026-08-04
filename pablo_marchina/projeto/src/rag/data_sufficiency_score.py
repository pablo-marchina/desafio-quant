"""data sufficiency score

Hypothesis: Evaluate whether data sufficiency score improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DataSufficiencyScore:
    """data sufficiency score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        total = len(contexts)
        sufficient = sum(1 for c in contexts if c.relevance_score > 0.3 and len(c.content) > 50)

        ratio = sufficient / max(total, 1)

        if not getattr(self, "_sufficiency_threshold", None):
            self._sufficiency_threshold = self.config.get("threshold", 0.5)

        for ctx in contexts:
            if ratio < self._sufficiency_threshold:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

        return contexts
