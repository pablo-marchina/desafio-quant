"""insufficient corpus coverage report

Hypothesis: Evaluate whether insufficient corpus coverage report improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class InsufficientCorpusCoverageReport:
    """insufficient corpus coverage report"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_coverage_stats", None):
            self._coverage_stats: dict[str, int] = {}

        for ctx in contexts:
            for gap in ctx.gap_types:
                self._coverage_stats[gap] = self._coverage_stats.get(gap, 0) + 1

        min_coverage = self.config.get("min_per_gap", 3)

        for ctx in contexts:
            for gap in ctx.gap_types:
                if self._coverage_stats.get(gap, 0) < min_coverage:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.08)

        return contexts
