"""Reviewer agent — review contexts for quality."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ReviewerAgentConfig(BaseModel):
    min_quality_score: float = 0.3


class ReviewerAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ReviewerAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _review(self, ctx: RetrievedContext) -> float:
        completeness = min(1.0, len(ctx.content.split()) / 100)
        source_quality = 0.2 if ctx.url else 0.0
        gap_coverage = min(0.3, len(ctx.gap_types) * 0.1)
        return round(0.4 * completeness + 0.3 * source_quality + 0.3 * gap_coverage, 4)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            review = self._review(ctx)
            ctx.relevance_score = round(0.6 * ctx.relevance_score + 0.4 * review, 4)
        return [ctx for ctx in contexts if ctx.relevance_score >= self.cfg.min_quality_score]
