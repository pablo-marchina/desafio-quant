"""Hierarchical node retrieval — hierarchical graph retrieval."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class HierarchicalNodeRetrievalConfig(BaseModel):
    top_level_count: int = 3
    detail_level_count: int = 5


class HierarchicalNodeRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = HierarchicalNodeRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts
        scored = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        top = scored[: self.cfg.top_level_count]
        detail = scored[self.cfg.top_level_count : self.cfg.top_level_count + self.cfg.detail_level_count]
        for ctx in top:
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.15), 4)
        for ctx in detail:
            ctx.relevance_score = round(ctx.relevance_score, 4)
        return top + detail
