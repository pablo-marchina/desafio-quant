from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DecisionRanking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            confidence = min(len(ctx.content.split()) / 200.0, 1.0)

            source_quality = 0.8 if ctx.url else 0.3

            impact = ctx.relevance_score * 0.5 + confidence * 0.3 + source_quality * 0.2

            ctx.relevance_score = round(min(1.0, impact), 4)

            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts
