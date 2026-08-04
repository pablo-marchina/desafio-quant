"""Segment-level regeneration — regenerate segments."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SegmentLevelRegenerationConfig(BaseModel):
    regeneration_multiplier: float = 1.1


class SegmentLevelRegeneration:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SegmentLevelRegenerationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        result = []
        for ctx in contexts:
            sentences = [
                s.strip() for s in ctx.content.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 20
            ]
            for i, sent in enumerate(sentences):
                seg = ctx.model_copy(deep=True)
                seg.content = sent + "."
                seg.chunk_id = f"{ctx.chunk_id}_seg{i}"
                seg.relevance_score = round(min(1.0, ctx.relevance_score * (1.0 - i * 0.05)), 4)
                result.append(seg)
        return result
