"""State transition tracking — track state transitions across contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class StateTransitionTrackingConfig(BaseModel):
    transition_decay: float = 0.05


class StateTransitionTracking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = StateTransitionTrackingConfig.model_validate(config or {})
        self._prev_state: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        current_state: dict[str, float] = {}
        for ctx in contexts:
            for g in ctx.gap_types:
                prev = self._prev_state.get(g, 0.0)

                delta = abs(ctx.relevance_score - prev)

                current_state[g] = ctx.relevance_score

                transition_penalty = delta * self.cfg.transition_decay

                ctx.relevance_score = round(max(0.0, ctx.relevance_score - transition_penalty), 4)

                self._prev_state = current_state
        return contexts
