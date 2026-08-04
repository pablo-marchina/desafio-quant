"""Agent recovery evaluation — evaluate recovery from failures."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgentRecoveryEvaluationConfig(BaseModel):
    recovery_multiplier: float = 1.2


class AgentRecoveryEvaluation:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgentRecoveryEvaluationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if ctx.relevance_score < 0.3:
                penalty = ctx.relevance_score * 0.1

                ctx.relevance_score = round(max(0.0, ctx.relevance_score - penalty), 4)

            elif ctx.relevance_score > 0.7:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * self.cfg.recovery_multiplier), 4)

        return contexts
