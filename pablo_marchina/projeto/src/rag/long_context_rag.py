from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LongContextRAGConfig(BaseModel):
    enabled: bool = True
    max_total_chars: int = 8000
    truncation_strategy: str = "score"  # score, first, balanced


class LongContextRAG:
    def __init__(self, config: Any | None = None) -> None:
        self.config = LongContextRAGConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        total = sum(len(c.content) for c in contexts)
        if total <= self.config.max_total_chars:
            return contexts
        if self.config.truncation_strategy == "score":
            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
            result: list[RetrievedContext] = []
            running = 0
            for ctx in contexts:
                if running + len(ctx.content) <= self.config.max_total_chars:
                    result.append(ctx)
                    running += len(ctx.content)
            return result
        elif self.config.truncation_strategy == "first":
            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        running = 0
        for ctx in contexts:
            needed = self.config.max_total_chars - running
            if needed <= 0:
                ctx.content = ""
            elif len(ctx.content) > needed:
                ctx.content = ctx.content[:needed] + "..."
                running = self.config.max_total_chars
            else:
                running += len(ctx.content)
        return [c for c in contexts if c.content]
