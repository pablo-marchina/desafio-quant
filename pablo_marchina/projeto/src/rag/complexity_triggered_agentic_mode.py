"""Complexity-triggered agentic mode — detect complexity and switch mode."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ComplexityTriggeredAgenticModeConfig(BaseModel):
    complexity_threshold: float = 0.5


class ComplexityTriggeredAgenticMode:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ComplexityTriggeredAgenticModeConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _measure_complexity(self, ctx: RetrievedContext) -> float:
        content_len = min(1.0, len(ctx.content) / 5000)
        gap_diversity = min(1.0, len(ctx.gap_types) / 5)
        sentence_count = max(1, ctx.content.count("."))
        sentence_complexity = min(1.0, sentence_count / 50)
        return round(0.4 * content_len + 0.3 * gap_diversity + 0.3 * sentence_complexity, 4)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            complexity = self._measure_complexity(ctx)

        if complexity > self.cfg.complexity_threshold:
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.15), 4)

        else:
            ctx.relevance_score = round(ctx.relevance_score, 4)

        return contexts
