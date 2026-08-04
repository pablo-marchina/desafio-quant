"""Agent step success rate — measure step success rate."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgentStepSuccessRateConfig(BaseModel):
    success_threshold: float = 0.5


class AgentStepSuccessRate:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgentStepSuccessRateConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        successes = sum(1 for ctx in contexts if ctx.relevance_score >= self.cfg.success_threshold)
        rate = successes / max(1, len(contexts))
        for ctx in contexts:
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * (0.8 + 0.2 * rate)), 4)

        return contexts
