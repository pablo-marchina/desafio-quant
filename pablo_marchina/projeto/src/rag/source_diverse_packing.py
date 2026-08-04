"""Source-diverse packing — pack with source diversity."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SourceDiversePackingConfig(BaseModel):
    max_per_source: int = 2


class SourceDiversePacking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SourceDiversePackingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        source_count: dict[str, int] = {}
        result = []
        for ctx in sorted(contexts, key=lambda c: c.relevance_score, reverse=True):
            sid = ctx.source_id
            if source_count.get(sid, 0) < self.cfg.max_per_source:
                source_count[sid] = source_count.get(sid, 0) + 1
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.05), 4)
                result.append(ctx)
            else:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.05), 4)
                result.append(ctx)
        return result
