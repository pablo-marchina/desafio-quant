"""Agent trajectory evaluation — evaluate agent trajectories."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgentTrajectoryEvaluationConfig(BaseModel):
    step_weight: float = 0.3
    outcome_weight: float = 0.7


class AgentTrajectoryEvaluation:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgentTrajectoryEvaluationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for i, ctx in enumerate(contexts):
            step_progress = (i + 1) / max(1, len(contexts))

            trajectory_score = self.cfg.step_weight * step_progress + self.cfg.outcome_weight * ctx.relevance_score

            ctx.relevance_score = round(min(1.0, trajectory_score), 4)

        return contexts
