"""retrieved token usefulness

Hypothesis: Evaluate whether retrieved token usefulness improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrievedTokenUsefulness:
    """retrieved token usefulness"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            useful_content = sum(1 for w in ctx.content.split() if len(w) > 2)

            total_tokens = len(ctx.content.split())

            usefulness = useful_content / max(total_tokens, 1)

            ctx.relevance_score = min(1.0, ctx.relevance_score * 0.5 + usefulness * 0.5)

        return contexts
