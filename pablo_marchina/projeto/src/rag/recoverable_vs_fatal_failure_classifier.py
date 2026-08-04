"""recoverable vs fatal failure classifier

Hypothesis: Evaluate whether recoverable vs fatal failure classifier improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RecoverableVsFatalFailureClassifier:
    """recoverable vs fatal failure classifier"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        fatal_signals = ["fatal", "irrecoverable", "catastrophic", "terminated", "shutdown"]
        recoverable_signals = ["retry", "recoverable", "temporary", "retrying", "timeout"]

        for ctx in contexts:
            fatal_count = sum(1 for s in fatal_signals if s in ctx.content.lower())

            recoverable_count = sum(1 for s in recoverable_signals if s in ctx.content.lower())

            if fatal_count:
                ctx.relevance_score = max(0.0, ctx.relevance_score - fatal_count * 0.15)

            if recoverable_count:
                ctx.relevance_score = max(0.0, ctx.relevance_score - recoverable_count * 0.05)

        return contexts
