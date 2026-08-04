"""Belief state tracking — track belief states across contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class BeliefStateTrackingConfig(BaseModel):
    belief_decay: float = 0.1


class BeliefStateTracking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = BeliefStateTrackingConfig.model_validate(config or {})
        self._belief_state: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for key in self._belief_state:
            self._belief_state[key] *= 1.0 - self.cfg.belief_decay

            for ctx in contexts:
                words = [w.lower() for w in ctx.content.split() if len(w) > 3]

                for w in set(words):
                    self._belief_state[w] = min(1.0, self._belief_state.get(w, 0.0) + 0.1 * ctx.relevance_score)

                    ctx.relevance_score = round(
                        sum(self._belief_state.get(w, 0.0) for w in set(words)) / max(1, len(set(words))),
                        4,
                    )

        return contexts
