"""Report critic agent — critique composed reports."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ReportCriticAgentConfig(BaseModel):
    coherence_weight: float = 0.4
    coverage_weight: float = 0.4
    quality_weight: float = 0.2


class ReportCriticAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ReportCriticAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            unique_gaps = len(set(g for ctx in contexts for g in ctx.gap_types))
            unique_sources = len(set(ctx.source_id for ctx in contexts))
            total_score = sum(ctx.relevance_score for ctx in contexts)
            coherence = unique_gaps / max(1, len(contexts))
            coverage = unique_sources / max(1, len(contexts))
            quality = total_score / max(1, len(contexts))
            report_score = (
                self.cfg.coherence_weight * coherence
                + self.cfg.coverage_weight * coverage
                + self.cfg.quality_weight * quality
            )
            for ctx in contexts:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.8 + 0.2 * report_score)), 4)

        return contexts
