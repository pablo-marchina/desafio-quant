"""Planner-Retriever-Verifier-Writer-Auditor multi-step pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class PlannerRetrieverVerifierWriterAuditorLoopConfig(BaseModel):
    audit_threshold: float = 0.35


class PlannerRetrieverVerifierWriterAuditorLoop:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = PlannerRetrieverVerifierWriterAuditorLoopConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        for ctx in contexts:
            plan = 0.1 * len(ctx.gap_types)
            retrieval = 0.2 if ctx.url else 0.0
            verify = ctx.relevance_score
            writer = min(0.2, len(ctx.content) / 5000 * 0.2)
            auditor = (verify + plan + retrieval + writer) / 4
            ctx.relevance_score = round(
                max(0.0, min(1.0, auditor)),
                4,
            )
        if query:
            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return [c for c in contexts if c.relevance_score >= self.cfg.audit_threshold]
