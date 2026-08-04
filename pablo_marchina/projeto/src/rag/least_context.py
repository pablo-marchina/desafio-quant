from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LeastContextRetrieverConfig(BaseModel):
    enabled: bool = True
    max_chunks: int = 3
    min_relevance: float = 0.1


class LeastContextRetriever:
    def __init__(self, config: Any | None = None) -> None:
        self.config = LeastContextRetrieverConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        sorted_ctx = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        selected: list[RetrievedContext] = []
        seen_content: set[str] = set()
        for ctx in sorted_ctx:
            if len(selected) >= self.config.max_chunks:
                break
            if ctx.relevance_score < self.config.min_relevance:
                continue
            content_folded = ctx.content.strip().lower()
            if content_folded in seen_content:
                continue
            seen_content.add(content_folded)
            selected.append(ctx)
        return selected
