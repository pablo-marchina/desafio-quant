"""Context priority scoring — score context priority."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ContextPriorityScoringConfig(BaseModel):
    recency_weight: float = 0.2
    relevance_weight: float = 0.5
    completeness_weight: float = 0.3


class ContextPriorityScoring:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ContextPriorityScoringConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for i, ctx in enumerate(contexts):
            recency = 1.0 - (i / max(1, len(contexts)))

            completeness = min(1.0, len(ctx.content) / 2000)

            priority = (
                self.cfg.recency_weight * recency
                + self.cfg.relevance_weight * ctx.relevance_score
                + self.cfg.completeness_weight * completeness
            )

            ctx.relevance_score = round(min(1.0, priority), 4)

        return contexts
