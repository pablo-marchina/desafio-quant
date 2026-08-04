from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class HybridSearchConfig(BaseModel):
    enabled: bool = True
    alpha: float = 0.5


class HybridSearch:
    def __init__(self, config: Any | None = None) -> None:
        self.config = HybridSearchConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        dense_scores: dict[str, float] = kwargs.get("dense_scores", {})
        sparse_scores: dict[str, float] = kwargs.get("sparse_scores", {})
        if not dense_scores and not sparse_scores:
            return contexts

            alpha = kwargs.get("alpha", self.config.alpha)
            for ctx in contexts:
                dense = dense_scores.get(ctx.chunk_id, 0.0)

                sparse = sparse_scores.get(ctx.chunk_id, 0.0)

                combined = alpha * dense + (1.0 - alpha) * sparse

                ctx.relevance_score = round(min(max(combined, 0.0), 1.0), 4)

                contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts
