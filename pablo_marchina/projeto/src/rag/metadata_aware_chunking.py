from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class MetadataAwareChunkingConfig(BaseModel):
    enabled: bool = True
    include_source: bool = True
    include_gap_types: bool = True
    include_product: bool = True
    include_relevance: bool = True


class MetadataAwareChunking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = MetadataAwareChunkingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            ctx.content = self._enrich(ctx)

        return contexts

    def _enrich(self, ctx: RetrievedContext) -> str:
        meta_parts: list[str] = []
        if self.config.include_source and ctx.title:
            meta_parts.append(f"Source: {ctx.title}")
        if self.config.include_gap_types and ctx.gap_types:
            meta_parts.append(f"Category: {', '.join(ctx.gap_types)}")
        if self.config.include_product and ctx.product:
            meta_parts.append(f"Product: {ctx.product}")
        if self.config.include_relevance:
            meta_parts.append(f"Relevance: {ctx.relevance_score:.2f}")
        prefix = " | ".join(meta_parts)
        if prefix:
            return f"[{prefix}]\n{ctx.content}"
        return ctx.content
