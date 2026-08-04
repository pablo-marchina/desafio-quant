"""coverage gap detector

Hypothesis: Evaluate whether coverage gap detector improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CoverageGapDetector:
    """coverage gap detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_all_gaps", None):
            self._all_gaps: dict[str, set[str]] = {}

        for ctx in contexts:
            for g in ctx.gap_types:
                if g not in self._all_gaps:
                    self._all_gaps[g] = set()

                self._all_gaps[g].add(ctx.source_id)

        for ctx in contexts:
            uncovered_gaps = [g for g, sources in self._all_gaps.items() if len(sources) < 2]

            if any(g in ctx.gap_types for g in uncovered_gaps):
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.08)

        return contexts
