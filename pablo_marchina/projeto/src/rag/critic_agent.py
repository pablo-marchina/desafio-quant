"""Critic agent — critique context quality across dimensions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CriticAgentConfig(BaseModel):
    completeness_weight: float = 0.3
    relevance_weight: float = 0.4
    source_weight: float = 0.3


class CriticAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CriticAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            completeness = min(1.0, len(ctx.content) / 1000)

            source = 0.2 if ctx.url else 0.0

            critique_score = (
                self.cfg.completeness_weight * completeness
                + self.cfg.relevance_weight * ctx.relevance_score
                + self.cfg.source_weight * source
            )

        if critique_score < 0.3:
            ctx.relevance_score = round(ctx.relevance_score * 0.8, 4)

        elif critique_score > 0.7:
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.1), 4)

        return contexts
