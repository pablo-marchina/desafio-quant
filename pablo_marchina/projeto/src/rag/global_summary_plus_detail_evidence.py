"""Global summary plus detail evidence — summary + details."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GlobalSummaryPlusDetailEvidenceConfig(BaseModel):
    summary_count: int = 2
    detail_count: int = 4


class GlobalSummaryPlusDetailEvidence:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GlobalSummaryPlusDetailEvidenceConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scored = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        summaries = scored[: self.cfg.summary_count]
        details = scored[self.cfg.summary_count : self.cfg.summary_count + self.cfg.detail_count]
        for ctx in summaries:
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.15), 4)
        return summaries + details
