"""Long-context direct reading — direct reading of long contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LongContextDirectReadingConfig(BaseModel):
    max_chars: int = 10000
    chunk_size: int = 2000


class LongContextDirectReading:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LongContextDirectReadingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        total_chars = 0
        result = []
        for ctx in contexts:
            content_len = len(ctx.content)
            if total_chars + content_len <= self.cfg.max_chars:
                total_chars += content_len
                ctx.relevance_score = round(
                    min(1.0, ctx.relevance_score * (1.0 + content_len / self.cfg.max_chars * 0.1)), 4
                )
                result.append(ctx)
            else:
                allowed = self.cfg.max_chars - total_chars
                if allowed > 0:
                    ctx.content = ctx.content[:allowed]
                    ctx.relevance_score = round(ctx.relevance_score * 0.9, 4)
                    result.append(ctx)
                break
        return result
