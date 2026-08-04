"""Autonomous loop kill-switch — kill switch for autonomous loops."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AutonomousLoopKillSwitchConfig(BaseModel):
    max_steps: int = 10
    diminishing_threshold: float = 0.005


class AutonomousLoopKillSwitch:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AutonomousLoopKillSwitchConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        steps = min(self.cfg.max_steps, len(contexts))
        for i in range(steps - 1):
            if i >= len(contexts) - 1:
                break

                delta = abs(contexts[i + 1].relevance_score - contexts[i].relevance_score)

                if delta < self.cfg.diminishing_threshold:
                    for ctx in contexts[i:]:
                        ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.02), 4)

                        break

        return contexts
