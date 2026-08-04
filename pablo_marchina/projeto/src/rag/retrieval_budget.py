"""Retrieval budget — manage retrieval budget."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class RetrievalBudgetAllocatorConfig(BaseModel):
    max_token_budget: int = 4096
    per_context_tokens: int = 512


class RetrievalBudgetAllocator:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = RetrievalBudgetAllocatorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        budget = self.cfg.max_token_budget
        result = []
        for ctx in sorted(contexts, key=lambda c: c.relevance_score, reverse=True):
            tokens = self.cfg.per_context_tokens + len(ctx.content) // 4
            if budget >= tokens:
                budget -= tokens
                result.append(ctx)
            else:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.15), 4)
                result.append(ctx)
        return result
