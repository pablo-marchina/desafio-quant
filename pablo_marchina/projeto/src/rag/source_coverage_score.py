"""source coverage score

Hypothesis: Evaluate whether source coverage score improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceCoverageScore:
    """source coverage score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_coverage", None):
            self._coverage: dict[str, int] = {}

        for ctx in contexts:
            gap_key = ctx.gap_types[0] if ctx.gap_types else "general"

            self._coverage[gap_key] = self._coverage.get(gap_key, 0) + 1

        total = sum(self._coverage.values())

        for ctx in contexts:
            gap_key = ctx.gap_types[0] if ctx.gap_types else "general"

            gap_count = self._coverage.get(gap_key, 0)

            gap_score = gap_count / max(total, 1)

            ctx.relevance_score = min(1.0, ctx.relevance_score * 0.7 + gap_score * 0.3)

        return contexts
