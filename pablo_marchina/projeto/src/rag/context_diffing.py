"""Context diffing — diff between context sets."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ContextDiffingConfig(BaseModel):
    novelty_bonus: float = 0.1
    redundancy_penalty: float = 0.05


class ContextDiffing:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ContextDiffingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        seen_content: set[str] = set()
        result = []
        for ctx in contexts:
            content_sig = ctx.content[:200]
            if content_sig not in seen_content:
                seen_content.add(content_sig)
                ctx.relevance_score = round(min(1.0, ctx.relevance_score + self.cfg.novelty_bonus), 4)
                result.append(ctx)
            else:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - self.cfg.redundancy_penalty), 4)
                result.append(ctx)
        return result
