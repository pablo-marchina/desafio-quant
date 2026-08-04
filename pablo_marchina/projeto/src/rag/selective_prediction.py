from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SelectivePrediction:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = float(config.get("threshold", 0.5)) if isinstance(config, dict) else 0.5

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                if ctx.relevance_score < self._threshold:
                    ctx.relevance_score = round(ctx.relevance_score * 0.3, 4)

        return contexts
