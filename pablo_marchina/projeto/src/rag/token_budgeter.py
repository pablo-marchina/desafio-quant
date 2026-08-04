"""Token budgeter — token budget management."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class TokenBudgeterConfig(BaseModel):
    max_tokens: int = 4096
    tokens_per_word: float = 1.3


class TokenBudgeter:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = TokenBudgeterConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        result = []
        budget = self.cfg.max_tokens
        for ctx in sorted(contexts, key=lambda c: c.relevance_score, reverse=True):
            tokens = int(len(ctx.content.split()) * self.cfg.tokens_per_word) + 10
            if budget >= tokens:
                budget -= tokens
                result.append(ctx)
            else:
                ratio = budget / max(1, tokens)
                words = ctx.content.split()
                max_words = max(1, int(len(words) * ratio))
                ctx.content = " ".join(words[:max_words])
                ctx.relevance_score = round(ctx.relevance_score * ratio, 4)
                if ctx.content:
                    result.append(ctx)
                break
        return result
