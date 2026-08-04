"""evidence-only answer mode

Hypothesis: Evaluate whether evidence-only answer mode improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class EvidenceOnlyAnswerMode:
    """evidence-only answer mode"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        min_evidence = self.config.get("min_evidence", 0.3)
        return [ctx for ctx in contexts if ctx.relevance_score >= min_evidence]

        return contexts
