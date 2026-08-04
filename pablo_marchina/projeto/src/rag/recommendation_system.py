from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class RecommendationSystemConfig(BaseModel):
    enabled: bool = True
    similarity_threshold: float = 0.2
    max_recommendations: int = 5


class RecommendationSystem:
    def __init__(self, config: Any | None = None) -> None:
        self.config = RecommendationSystemConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        target: str = kwargs.get("query", "")
        if not target:
            return contexts
        target_lower = target.lower()
        target_tokens = set(target_lower.split())
        scored: list[tuple[RetrievedContext, float]] = []
        for ctx in contexts:
            ctx_tokens = set(ctx.content.lower().split())
            overlap = len(target_tokens & ctx_tokens)
            union = len(target_tokens | ctx_tokens)
            jaccard = overlap / union if union > 0 else 0.0
            product_match = 1.0 if ctx.product.lower() in target_lower else 0.0
            sim = jaccard * 0.6 + product_match * 0.4
            scored.append((ctx, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        result = [ctx for ctx, sim in scored if sim >= self.config.similarity_threshold]
        for ctx in result:
            ctx.relevance_score = round(min(ctx.relevance_score + 0.1, 1.0), 4)
        return result[: self.config.max_recommendations]
