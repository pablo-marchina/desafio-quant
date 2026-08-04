"""Program-of-Thought — generate program-like reasoning steps for contexts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ProgramOfThoughtConfig(BaseModel):
    step_count: int = 3


class ProgramOfThought:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ProgramOfThoughtConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            words = ctx.content.split()

            char_count = sum(len(w) for w in words)

            step_score = min(1.0, char_count / (self.cfg.step_count * 500))

            ctx.relevance_score = round(0.6 * ctx.relevance_score + 0.4 * step_score, 4)

        return contexts
