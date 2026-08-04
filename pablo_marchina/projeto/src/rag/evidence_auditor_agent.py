"""Evidence auditor agent — audit evidence quality across contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class EvidenceAuditorAgentConfig(BaseModel):
    min_evidence_score: float = 0.25


class EvidenceAuditorAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = EvidenceAuditorAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _audit(self, ctx: RetrievedContext) -> float:
        has_url = 0.2 if ctx.url else 0.0
        content_depth = min(0.3, len(ctx.content.split()) / 500 * 0.3)
        gap_coverage = min(0.3, len(ctx.gap_types) * 0.1)
        activeness = 0.2 if ctx.is_active else 0.0
        return round(has_url + content_depth + gap_coverage + activeness, 4)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            evidence = self._audit(ctx)
            ctx.relevance_score = round(0.5 * ctx.relevance_score + 0.5 * evidence, 4)
        return [ctx for ctx in contexts if ctx.relevance_score >= self.cfg.min_evidence_score]
