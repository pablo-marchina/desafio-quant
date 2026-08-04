"""Recency-weighted packing — recency-weighted packing."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class RecencyWeightedPackingConfig(BaseModel):
    recency_factor: float = 0.9


class RecencyWeightedPacking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = RecencyWeightedPackingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts
        scored = []
        for i, ctx in enumerate(contexts):
            recency_weight = self.cfg.recency_factor ** (len(contexts) - 1 - i)
            combined = 0.6 * ctx.relevance_score + 0.4 * recency_weight
            scored.append((combined, ctx))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ctx for _, ctx in scored]
