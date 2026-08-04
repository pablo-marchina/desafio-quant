from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ValueOfInformationConfig(BaseModel):
    enabled: bool = True
    novelty_weight: float = 0.3
    relevance_weight: float = 0.4
    diversity_weight: float = 0.3


class ValueOfInformation:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ValueOfInformationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for i, ctx in enumerate(contexts):
            info_gain = self._compute_info_gain(ctx, contexts[:i])

            ctx.relevance_score = round(min(ctx.relevance_score + info_gain, 1.0), 4)

            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts

    def _compute_info_gain(self, ctx: RetrievedContext, seen: list[RetrievedContext]) -> float:
        if not seen:
            return 0.2
        content = ctx.content.lower()
        ctx_tokens = set(content.split())
        seen_tokens = set()
        for s in seen:
            seen_tokens.update(s.content.lower().split())
        overlap = len(ctx_tokens & seen_tokens) / max(len(ctx_tokens), 1)
        novelty = 1.0 - overlap
        return self.config.novelty_weight * novelty + self.config.relevance_weight * ctx.relevance_score
