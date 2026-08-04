"""known judge failure patterns

Hypothesis: Evaluate whether known judge failure patterns improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class KnownJudgeFailurePatterns:
    """known judge failure patterns"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        patterns = [
            "cannot determine",
            "unable to judge",
            "insufficient context",
            "no clear answer",
            "ambiguous",
            "both sides",
            "it is unclear",
            "hard to say",
        ]

        for ctx in contexts:
            fail_score = sum(1 for p in patterns if p.lower() in ctx.content.lower())

            if fail_score:
                ctx.relevance_score = max(0.0, ctx.relevance_score - fail_score * 0.06)

        return contexts
