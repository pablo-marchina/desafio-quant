"""Autonomous search trajectory evaluation — evaluate search trajectories."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AutonomousSearchTrajectoryEvalConfig(BaseModel):
    trajectory_length_weight: float = 0.3
    score_improvement_weight: float = 0.7


class AutonomousSearchTrajectoryEval:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AutonomousSearchTrajectoryEvalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if len(contexts) < 2:
            return contexts

            scores = [ctx.relevance_score for ctx in contexts]
            improvement = max(0.0, scores[-1] - scores[0])
            trajectory_score = self.cfg.trajectory_length_weight * (len(contexts) / 10)
            trajectory_score += self.cfg.score_improvement_weight * improvement
            for ctx in contexts:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.9 + 0.1 * trajectory_score)), 4)

        return contexts
