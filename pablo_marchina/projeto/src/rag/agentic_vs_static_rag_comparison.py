"""Agentic-vs-static RAG comparison — compare agentic vs static RAG."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgenticVsStaticRagComparisonConfig(BaseModel):
    agentic_boost: float = 0.1


class AgenticVsStaticRagComparison:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgenticVsStaticRagComparisonConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        [ctx.relevance_score for ctx in contexts]
        if not contexts:
            return contexts

            for ctx in contexts:
                overlap = len(set(ctx.gap_types))

                improvement = overlap * 0.05

                ctx.relevance_score = round(min(1.0, ctx.relevance_score + self.cfg.agentic_boost + improvement), 4)

        return contexts
