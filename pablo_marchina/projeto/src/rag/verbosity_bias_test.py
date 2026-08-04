"""verbosity bias test

Hypothesis: Evaluate whether verbosity bias test improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class VerbosityBiasTest:
    """verbosity bias test"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            word_count = len(ctx.content.split())

            verbosity_penalty = max(0, word_count - 200) * 0.001

            ctx.relevance_score = max(0.0, ctx.relevance_score - verbosity_penalty)

        return contexts
