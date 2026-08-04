"""knowledge gap detector

Hypothesis: Evaluate whether knowledge gap detector improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class KnowledgeGapDetector:
    """knowledge gap detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        gap_signals = [
            "unknown",
            "unclear",
            "not available",
            "further research",
            "not specified",
            "to be determined",
            "tbd",
            "insufficient",
        ]

        for ctx in contexts:
            gap_count = sum(1 for g in gap_signals if g in ctx.content.lower())

            if gap_count:
                ctx.relevance_score = max(0.0, ctx.relevance_score - gap_count * 0.08)

        return contexts
