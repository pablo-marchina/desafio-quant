"""Least-to-most prompting — process from easiest to hardest context."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LeastToMostPromptingConfig(BaseModel):
    ascending: bool = True


class LeastToMostPrompting:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LeastToMostPromptingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scored = []
        for ctx in contexts:
            difficulty = 1.0 - ctx.relevance_score
            content_len = len(ctx.content)
            complexity = min(1.0, content_len / 5000)
            overall = 0.5 * difficulty + 0.5 * complexity
            scored.append((overall, ctx))
        scored.sort(key=lambda x: x[0], reverse=not self.cfg.ascending)
        return [ctx for _, ctx in scored]
