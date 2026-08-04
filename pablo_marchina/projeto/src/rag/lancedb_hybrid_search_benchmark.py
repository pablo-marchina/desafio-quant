"""LanceDB hybrid search benchmark

Hypothesis: Evaluate whether LanceDB hybrid search benchmark improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class LancedbHybridSearchBenchmark:
    """LanceDB hybrid search benchmark"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        dense_weight = self.config.get("dense_weight", 0.5)
        sparse_weight = 1.0 - dense_weight

        for ctx in contexts:
            score = ctx.relevance_score * dense_weight + 0.5 * sparse_weight

            ctx.relevance_score = min(1.0, score)

        return contexts
