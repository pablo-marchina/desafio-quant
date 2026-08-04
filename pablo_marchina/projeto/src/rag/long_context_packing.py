"""Long-context packing — pack long contexts efficiently."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LongContextPackingConfig(BaseModel):
    target_tokens: int = 4096
    overhead_per_context: int = 50


class LongContextPacking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LongContextPackingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        budget = self.cfg.target_tokens
        result = []
        for ctx in sorted(contexts, key=lambda c: c.relevance_score, reverse=True):
            tokens = len(ctx.content.split()) + self.cfg.overhead_per_context
            if budget >= tokens:
                budget -= tokens
                result.append(ctx)
            elif budget > self.cfg.overhead_per_context:
                max_words = budget - self.cfg.overhead_per_context
                words = ctx.content.split()[:max_words]
                ctx.content = " ".join(words)
                result.append(ctx)
                break
        return result
