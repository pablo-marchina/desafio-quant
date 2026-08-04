"""Adaptive number of retrieval rounds — adapt rounds based on context."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class AdaptiveNumberOfRetrievalRoundsConfig(BaseModel):
    max_rounds: int = 5
    min_rounds: int = 1


class AdaptiveNumberOfRetrievalRounds:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = AdaptiveNumberOfRetrievalRoundsConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            var_score = 0.0
            if len(contexts) > 1:
                scores = [ctx.relevance_score for ctx in contexts]

                mean = sum(scores) / len(scores)

                var_score = sum((s - mean) ** 2 for s in scores) / len(scores)

                needed_rounds = round(
                    self.cfg.min_rounds + (self.cfg.max_rounds - self.cfg.min_rounds) * min(1.0, var_score * 5)
                )
                for ctx in contexts:
                    multiplier = 1.0 + (needed_rounds / self.cfg.max_rounds) * 0.1

                    ctx.relevance_score = round(min(1.0, ctx.relevance_score * multiplier), 4)

        return contexts
