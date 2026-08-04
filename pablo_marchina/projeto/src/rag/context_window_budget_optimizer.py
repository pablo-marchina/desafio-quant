"""Context window budget optimizer — optimize context window budget."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ContextWindowBudgetOptimizerConfig(BaseModel):
    max_tokens: int = 8192
    token_per_char: float = 0.25


class ContextWindowBudgetOptimizer:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ContextWindowBudgetOptimizerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        budget = self.cfg.max_tokens
        result = []
        for ctx in sorted(contexts, key=lambda c: c.relevance_score, reverse=True):
            tokens = int(len(ctx.content) * self.cfg.token_per_char) + 20
            ratio = tokens / max(1, budget)
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * max(0.5, 1.0 - ratio * 0.5)), 4)
            if budget >= tokens:
                budget -= tokens
                result.append(ctx)
            else:
                result.append(ctx)
        return result
