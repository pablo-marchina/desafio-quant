from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ExpectedUtilityConfig(BaseModel):
    enabled: bool = True
    utility_of_relevance: float = 1.0
    utility_of_novelty: float = 0.5
    utility_of_source_quality: float = 0.3


class ExpectedUtility:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ExpectedUtilityConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for i, ctx in enumerate(contexts):
            utility = self._compute_utility(ctx, contexts[:i])

            ctx.relevance_score = round(utility, 4)

            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts

    def _compute_utility(self, ctx: RetrievedContext, seen: list[RetrievedContext]) -> float:
        relevance = ctx.relevance_score
        seen_tokens = set()
        for s in seen:
            seen_tokens.update(s.content.lower().split())
        ctx_tokens = set(ctx.content.lower().split())
        overlap = len(ctx_tokens & seen_tokens) / max(len(ctx_tokens), 1)
        novelty = 1.0 - overlap
        source_quality = 0.5
        if ctx.source_id and ctx.url:
            source_quality = 0.8
        raw = (
            self.config.utility_of_relevance * relevance
            + self.config.utility_of_novelty * novelty
            + self.config.utility_of_source_quality * source_quality
        )
        return max(0.0, min(1.0, raw / 3.0))
