from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CheapModelFirstRouting:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        complexity_threshold = self.config.get("complexity_threshold", 0.4)
        for ctx in contexts:
            complexity = min(len(ctx.content.split()) / 500.0, 1.0)

        if complexity <= complexity_threshold:
            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

        else:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
