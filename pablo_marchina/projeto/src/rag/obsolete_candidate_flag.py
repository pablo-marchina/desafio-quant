"""obsolete candidate flag

Hypothesis: Evaluate whether obsolete candidate flag improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ObsoleteCandidateFlag:
    """obsolete candidate flag"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        obsolescence_signals = [
            "superseded",
            "deprecated",
            "obsolete",
            "replaced",
            "old version",
            "legacy",
            "no longer supported",
        ]

        for ctx in contexts:
            if any(o in ctx.content.lower() for o in obsolescence_signals):
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

        return contexts
