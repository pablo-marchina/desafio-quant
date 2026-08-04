"""Typesense

Hypothesis: Evaluate whether Typesense improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Typesense:
    """Typesense"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        prefix_weight = self.config.get("prefix_weight", 0.3)
        for ctx in contexts:
            prefix_match = kwargs.get("prefix_match", False)

            score = ctx.relevance_score * (1 - prefix_weight)

            if prefix_match:
                score += prefix_weight

            ctx.relevance_score = min(1.0, score)

        return contexts
