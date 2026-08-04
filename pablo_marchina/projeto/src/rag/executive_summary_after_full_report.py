"""Executive summary after full report — exec summary."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ExecutiveSummaryAfterFullReportConfig(BaseModel):
    summary_ratio: float = 0.3


class ExecutiveSummaryAfterFullReport:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ExecutiveSummaryAfterFullReportConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts
        total = len(contexts)
        summary_count = max(1, int(total * self.cfg.summary_ratio))
        scored = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        summaries = scored[:summary_count]
        details = scored[summary_count:]
        for ctx in summaries:
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.15), 4)
        return summaries + details
