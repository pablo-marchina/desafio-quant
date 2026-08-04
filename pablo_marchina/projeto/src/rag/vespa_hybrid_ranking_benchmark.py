"""Vespa hybrid ranking benchmark

Hypothesis: Evaluate whether Vespa hybrid ranking benchmark improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class VespaHybridRankingBenchmark:
    """Vespa hybrid ranking benchmark"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        alpha = self.config.get("alpha", 0.3)
        for ctx in contexts:
            native_score = ctx.relevance_score

            weighted = native_score * (1 - alpha) + (0.5 * alpha)

            ctx.relevance_score = min(1.0, weighted)

        return contexts
