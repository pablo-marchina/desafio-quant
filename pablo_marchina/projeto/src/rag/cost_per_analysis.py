from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CostPerAnalysis:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        input_tokens = sum(len(ctx.content.split()) for ctx in contexts)
        output_estimate = self.config.get("estimated_output_tokens", 256)
        cost = (input_tokens * 0.00001) + (output_estimate * 0.00002)
        for ctx in contexts:
            ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score - cost * 0.1))

        return contexts
