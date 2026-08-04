"""Curator agent — curate and select the best contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CuratorAgentConfig(BaseModel):
    max_contexts: int = 10
    diversity_weight: float = 0.3


class CuratorAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CuratorAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scored = []
        seen_sources = set()
        for ctx in contexts:
            relevance = ctx.relevance_score
            diversity_bonus = 0.0
            if ctx.source_id not in seen_sources:
                diversity_bonus = self.cfg.diversity_weight
                seen_sources.add(ctx.source_id)
            combined = relevance + diversity_bonus
            scored.append((combined, ctx))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ctx for _, ctx in scored[: self.cfg.max_contexts]]
