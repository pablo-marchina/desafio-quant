"""Agentic benchmark coverage map — map benchmark coverage."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgenticBenchmarkCoverageMapConfig(BaseModel):
    coverage_bonus: float = 0.05


class AgenticBenchmarkCoverageMap:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgenticBenchmarkCoverageMapConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        all_gaps = set(g for ctx in contexts for g in ctx.gap_types)
        for ctx in contexts:
            covered = sum(1 for g in ctx.gap_types if g in all_gaps)

            coverage = covered / max(1, len(all_gaps))

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + coverage * self.cfg.coverage_bonus), 4)

        return contexts
