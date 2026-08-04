"""commercial startup intelligence baseline

Hypothesis: Evaluate whether commercial startup intelligence baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CommercialStartupIntelligenceBaseline:
    """commercial startup intelligence baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        startup_signals = [
            "series",
            "funding",
            "revenue",
            "valuation",
            "seed",
            "growth",
            "startup",
            "founder",
            "investor",
        ]

        for ctx in contexts:
            signal_count = sum(1 for s in startup_signals if s.lower() in ctx.content.lower())

            ctx.relevance_score = signal_count / max(len(startup_signals), 1)

        return contexts
