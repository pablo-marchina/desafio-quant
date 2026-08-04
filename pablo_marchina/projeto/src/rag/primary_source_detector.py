"""primary source detector

Hypothesis: Evaluate whether primary source detector improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PrimarySourceDetector:
    """primary source detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        primary_hints = [
            "original",
            "official",
            "primary",
            "source code",
            "documentation",
            "whitepaper",
            "technical report",
            "spec",
        ]

        for ctx in contexts:
            hint_count = sum(
                1 for h in primary_hints if h.lower() in ctx.content.lower() or h.lower() in ctx.title.lower()
            )

            if hint_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + hint_count * 0.06)

        return contexts
