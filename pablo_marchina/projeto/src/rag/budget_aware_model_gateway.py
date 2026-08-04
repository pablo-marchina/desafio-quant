from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class BudgetAwareModelGateway:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        budget = self.config.get("budget", 1000)
        total_tokens = sum(len(ctx.content.split()) for ctx in contexts)
        token_cost = total_tokens * 0.001
        for ctx in contexts:
            if token_cost > budget:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

        else:
            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
