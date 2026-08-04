"""LongRAG — LongRAG implementation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LongragConfig(BaseModel):
    window_size: int = 1000
    stride: int = 500


class Longrag:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LongragConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        result = []
        for ctx in contexts:
            words = ctx.content.split()
            for start in range(0, len(words), self.cfg.stride):
                window = words[start : start + self.cfg.window_size]
                if not window:
                    continue
                chunk = ctx.model_copy(deep=True)
                chunk.content = " ".join(window)
                chunk.chunk_id = f"{ctx.chunk_id}_win{start}"
                if query:
                    overlap = len(set(query.lower().split()) & set(chunk.content.lower().split()))
                    window_score = overlap / max(1, len(query.split()))
                else:
                    window_score = ctx.relevance_score * (1.0 - start / max(1, len(words)))
                chunk.relevance_score = round(min(1.0, window_score), 4)
                result.append(chunk)
        return result
