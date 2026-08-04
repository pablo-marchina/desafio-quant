"""Agent loop instability — detect loop instability."""

from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AgentLoopInstabilityConfig(BaseModel):
    instability_threshold: float = 0.3


class AgentLoopInstability:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AgentLoopInstabilityConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if len(contexts) < 3:
            return contexts

            scores = [ctx.relevance_score for ctx in contexts]
            variance = statistics.variance(scores) if len(scores) > 1 else 0.0
            instability = min(1.0, variance * 5)
            if instability > self.cfg.instability_threshold:
                avg = sum(scores) / len(scores)

                for ctx in contexts:
                    if ctx.relevance_score > avg:
                        ctx.relevance_score = round(max(0.0, ctx.relevance_score - instability * 0.05), 4)

                else:
                    ctx.relevance_score = round(min(1.0, ctx.relevance_score + instability * 0.05), 4)

        return contexts
