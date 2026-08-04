"""Critic-as-tool — use critic to evaluate contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CriticAsToolConfig(BaseModel):
    min_quality: float = 0.2


class CriticAsTool:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CriticAsToolConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _critic_score(self, ctx: RetrievedContext) -> float:
        completeness = min(1.0, len(ctx.content) / 500)
        gap_relevance = 0.1 * len(ctx.gap_types)
        provenance = 0.1 if ctx.url else 0.0
        return round(0.5 * completeness + 0.3 * gap_relevance + 0.2 * provenance, 4)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            critique = self._critic_score(ctx)
            ctx.relevance_score = round(max(0.0, ctx.relevance_score * 0.7 + critique * 0.3), 4)
        return [ctx for ctx in contexts if self._critic_score(ctx) >= self.cfg.min_quality]
