"""source coverage matrix

Hypothesis: Evaluate whether source coverage matrix improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceCoverageMatrix:
    """source coverage matrix"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_coverage_matrix", None):
            self._coverage_matrix: dict[str, set[str]] = {}

        for ctx in contexts:
            gap = ", ".join(ctx.gap_types) if ctx.gap_types else "general"

            if gap not in self._coverage_matrix:
                self._coverage_matrix[gap] = set()

            self._coverage_matrix[gap].add(ctx.source_id)

            coverage = len(self._coverage_matrix[gap])

            ctx.relevance_score = min(1.0, ctx.relevance_score + min(coverage * 0.02, 0.3))

        return contexts
