"""manual analyst baseline

Hypothesis: Evaluate whether manual analyst baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ManualAnalystBaseline:
    """manual analyst baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        analyst_signals = [
            "estimated",
            "projected",
            "approximately",
            "based on analysis",
            "industry report",
            "expert opinion",
        ]

        for ctx in contexts:
            signal_count = sum(1 for s in analyst_signals if s.lower() in ctx.content.lower())

            ctx.relevance_score = min(1.0, signal_count * 0.2)

        return contexts
