"""Finite-horizon retrieval policy — finite horizon planning."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class FiniteHorizonRetrievalPolicyConfig(BaseModel):
    horizon: int = 3


class FiniteHorizonRetrievalPolicy:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = FiniteHorizonRetrievalPolicyConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        horizon = min(self.cfg.horizon, len(contexts))
        if not contexts:
            return contexts

            top = contexts[:horizon]
            for ctx in top:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.1), 4)

                for ctx in contexts[horizon:]:
                    ctx.relevance_score = round(max(0.0, ctx.relevance_score * 0.95), 4)

        return contexts
