"""Agent planning capability score — score planning capability."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgentPlanningCapabilityScoreConfig(BaseModel):
    planning_weight: float = 0.3


class AgentPlanningCapabilityScore:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgentPlanningCapabilityScoreConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            avg_score = sum(ctx.relevance_score for ctx in contexts) / len(contexts)
            gap_diversity = len(set(g for ctx in contexts for g in ctx.gap_types)) / max(1, len(contexts))
            planning_score = (1.0 - self.cfg.planning_weight) * avg_score + self.cfg.planning_weight * gap_diversity
            for ctx in contexts:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.8 + 0.2 * planning_score)), 4)

        return contexts
