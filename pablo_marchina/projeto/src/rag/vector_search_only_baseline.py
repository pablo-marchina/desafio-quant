"""vector-search-only baseline

Hypothesis: Evaluate whether vector-search-only baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class VectorSearchOnlyBaseline:
    """vector-search-only baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        dense_scores = [ctx.relevance_score for ctx in contexts]
        if not dense_scores:
            return contexts

        max_s = max(dense_scores)

        for ctx in contexts:
            ctx.relevance_score = max(0.0, ctx.relevance_score / max_s) if max_s > 0 else 0.0

        return contexts
