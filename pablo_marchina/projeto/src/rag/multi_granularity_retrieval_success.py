"""Multi-granularity retrieval success — measure retrieval success."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class MultiGranularityRetrievalSuccessConfig(BaseModel):
    threshold_coarse: float = 0.4
    threshold_fine: float = 0.7


class MultiGranularityRetrievalSuccess:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = MultiGranularityRetrievalSuccessConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        coarse = sum(1 for ctx in contexts if ctx.relevance_score >= self.cfg.threshold_coarse)
        fine = sum(1 for ctx in contexts if ctx.relevance_score >= self.cfg.threshold_fine)
        coarse_rate = coarse / len(contexts)
        fine_rate = fine / len(contexts)
        for ctx in contexts:
            if ctx.relevance_score >= self.cfg.threshold_fine:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.9 + 0.1 * fine_rate)), 4)

            elif ctx.relevance_score >= self.cfg.threshold_coarse:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.9 + 0.1 * coarse_rate)), 4)

        return contexts
