"""source gap detector

Hypothesis: Evaluate whether source gap detector improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceGapDetector:
    """source gap detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_gap_coverage", None):
            self._gap_coverage: dict[str, int] = {}

        for ctx in contexts:
            for g in ctx.gap_types:
                self._gap_coverage[g] = self._gap_coverage.get(g, 0) + 1

        min_threshold = self.config.get("min_sources_per_gap", 2)

        for ctx in contexts:
            for g in ctx.gap_types:
                if self._gap_coverage.get(g, 0) < min_threshold:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

        return contexts
