"""Observation-state separation — separate observations from state."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ObservationStateSeparationConfig(BaseModel):
    state_weight: float = 0.6
    observation_weight: float = 0.4


class ObservationStateSeparation:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ObservationStateSeparationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            sentence_count = max(1, ctx.content.count(".") + ctx.content.count("!") + ctx.content.count("?"))

            obs_score = min(1.0, sentence_count / 20)

            word_count = len(ctx.content.split())

            state_score = min(1.0, word_count / 500)

            combined = self.cfg.state_weight * state_score + self.cfg.observation_weight * obs_score

            ctx.relevance_score = round(0.5 * ctx.relevance_score + 0.5 * combined, 4)

        return contexts
