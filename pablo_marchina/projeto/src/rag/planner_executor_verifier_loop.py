"""Planner-executor-verifier loop — plan then execute then verify."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class PlannerExecutorVerifierLoopConfig(BaseModel):
    max_loop: int = 3
    verification_threshold: float = 0.4


class PlannerExecutorVerifierLoop:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = PlannerExecutorVerifierLoopConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            for _ in range(self.cfg.max_loop):
                old = ctx.relevance_score

                plan = min(1.0, len(ctx.gap_types) * 0.15)

                exec_val = 0.5 * old + 0.3 * plan + 0.2 * (0.1 if ctx.url else 0.0)

                verified = exec_val >= self.cfg.verification_threshold

                ctx.relevance_score = round(exec_val, 4)

                if verified:
                    ctx.relevance_score = round(min(1.0, ctx.relevance_score + 0.05), 4)

                    if abs(ctx.relevance_score - old) < 0.01:
                        break

        return contexts
