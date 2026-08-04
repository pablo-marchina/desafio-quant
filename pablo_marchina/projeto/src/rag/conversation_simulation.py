"""Conversation simulation — simulate multi-turn conversation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ConversationSimulationConfig(BaseModel):
    turns: int = 3
    turn_decay: float = 0.1


class ConversationSimulation:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ConversationSimulationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            for t in range(self.cfg.turns):
                turn_boost = max(0.0, 1.0 - t * self.cfg.turn_decay)

                ctx.relevance_score = round(min(1.0, ctx.relevance_score + turn_boost * 0.05), 4)

                contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts
