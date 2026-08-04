"""Local-detail retrieval — retrieve local details."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LocalDetailRetrievalConfig(BaseModel):
    detail_bonus: float = 0.1


class LocalDetailRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LocalDetailRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            sentence_count = max(1, ctx.content.count("."))

            avg_sentence_len = len(ctx.content.split()) / sentence_count

            if 5 <= avg_sentence_len <= 30:
                detail_score = self.cfg.detail_bonus * (1.0 - abs(avg_sentence_len - 15) / 15)

                ctx.relevance_score = round(min(1.0, ctx.relevance_score + detail_score), 4)

        return contexts
