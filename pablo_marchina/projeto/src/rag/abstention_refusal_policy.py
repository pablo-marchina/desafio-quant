from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class AbstentionRefusalPolicy:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._min_score = float(config.get("min_score", 0.3)) if isinstance(config, dict) else 0.3

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            avg_score = sum(ctx.relevance_score for ctx in contexts) / max(len(contexts), 1)
            if avg_score < self._min_score:
                for ctx in contexts:
                    ctx.relevance_score = round(ctx.relevance_score * 0.5, 4)

        return contexts
