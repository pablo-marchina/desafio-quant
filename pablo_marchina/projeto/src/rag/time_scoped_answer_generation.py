"""time-scoped answer generation

Hypothesis: Evaluate whether time-scoped answer generation improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class TimeScopedAnswerGeneration:
    """time-scoped answer generation"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        time_scope = kwargs.get("time_scope", "")
        if not time_scope:
            return contexts

        scope_lower = time_scope.lower()

        for ctx in contexts:
            ts_str = ctx.valid_from or ctx.collected_at or ctx.content[:50]

            if "2024" in scope_lower and "2024" in ts_str:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.2)

            elif "2025" in scope_lower and "2025" in ts_str:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.2)

            elif scope_lower in ctx.content.lower():
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

        return contexts
