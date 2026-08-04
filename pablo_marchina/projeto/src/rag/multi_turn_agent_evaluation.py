"""Multi-turn agent evaluation — evaluate multi-turn agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class MultiTurnAgentEvaluationConfig(BaseModel):
    turn_weight: float = 0.2


class MultiTurnAgentEvaluation:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = MultiTurnAgentEvaluationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for i, ctx in enumerate(contexts):
            turn_score = 1.0 - (i / max(1, len(contexts))) * self.cfg.turn_weight

            ctx.relevance_score = round(0.7 * ctx.relevance_score + 0.3 * turn_score, 4)

        return contexts
