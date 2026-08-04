"""Context packer — general context packer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ContextPackerConfig(BaseModel):
    max_contexts: int = 8
    max_chars: int = 8000


class ContextPacker:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ContextPackerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scored = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        result: list[RetrievedContext] = []
        total_chars = 0
        for ctx in scored:
            if len(result) >= self.cfg.max_contexts:
                break
            if total_chars + len(ctx.content) > self.cfg.max_chars:
                continue
            total_chars += len(ctx.content)
            result.append(ctx)
        return result
