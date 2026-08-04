"""missing counterargument detector

Hypothesis: Evaluate whether missing counterargument detector improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MissingCounterargumentDetector:
    """missing counterargument detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        counter_signals = [
            "however",
            "but",
            "although",
            "nevertheless",
            "on the other hand",
            "conversely",
            "despite",
            "yet",
        ]

        for ctx in contexts:
            counter_count = sum(1 for c in counter_signals if c in ctx.content.lower())

            if counter_count == 0:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

            else:
                ctx.relevance_score = min(1.0, ctx.relevance_score + counter_count * 0.03)

        return contexts
