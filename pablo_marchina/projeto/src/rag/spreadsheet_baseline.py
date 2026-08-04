"""spreadsheet baseline

Hypothesis: Evaluate whether spreadsheet baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SpreadsheetBaseline:
    """spreadsheet baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        table_signals = [
            "table",
            "row",
            "column",
            "cell",
            "data",
            "value",
            "metric",
            "kpi",
            "figure",
            "chart",
            "spreadsheet",
        ]

        for ctx in contexts:
            signal_count = sum(1 for s in table_signals if s.lower() in ctx.content.lower())

            ctx.relevance_score = min(1.0, signal_count * 0.15)

        return contexts
