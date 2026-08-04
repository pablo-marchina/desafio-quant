"""dataset limitation disclosure

Hypothesis: Evaluate whether dataset limitation disclosure improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DatasetLimitationDisclosure:
    """dataset limitation disclosure"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_dataset_limitations", None):
            self._dataset_limitations: list[str] = []

        limitation = kwargs.get("dataset_limitation", "")

        if limitation:
            self._dataset_limitations.append(str(limitation))

        for ctx in contexts:
            penalty = len(self._dataset_limitations) * 0.02

            ctx.relevance_score = max(0.0, ctx.relevance_score - penalty)

        return contexts
