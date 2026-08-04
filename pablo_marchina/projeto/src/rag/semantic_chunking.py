from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext

_SEMANTIC_BOUNDARY_SIGNALS = [
    "in conclusion",
    "to summarize",
    "finally",
    "first",
    "second",
    "third",
    "introduction",
    "overview",
    "background",
    "prerequisites",
    "getting started",
    "installation",
    "configuration",
    "usage",
    "api reference",
    "examples",
    "troubleshooting",
    "faq",
    "see also",
    "related topics",
    "next steps",
]


class SemanticChunkingConfig(BaseModel):
    enabled: bool = True
    max_chunk_size: int = 1000
    min_chunk_size: int = 100


class SemanticChunking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = SemanticChunkingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        result: list[RetrievedContext] = []
        for ctx in contexts:
            chunks = self._rechunk(ctx)
            for i, chunk_content in enumerate(chunks):
                new_ctx = ctx.model_copy(deep=True)
                new_ctx.chunk_id = f"{ctx.chunk_id}_sc_{i}"
                new_ctx.content = chunk_content
                new_ctx.relevance_score = round(ctx.relevance_score * 0.95, 4)
                result.append(new_ctx)
        return result

    def _rechunk(self, ctx: RetrievedContext) -> list[str]:
        paragraphs = [p.strip() for p in ctx.content.split("\n\n") if p.strip()]
        if not paragraphs:
            return [ctx.content]
        segments: list[str] = []
        current: list[str] = []
        current_len = 0
        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > self.config.max_chunk_size and current:
                segments.append("\n\n".join(current))
                current = [para]
                current_len = para_len
            else:
                current.append(para)
                current_len += para_len
        if current:
            segments.append("\n\n".join(current))
        result: list[str] = []
        for seg in segments:
            if len(seg) < self.config.min_chunk_size and result:
                result[-1] = result[-1] + "\n\n" + seg
            else:
                result.append(seg)
        return result or [ctx.content]
