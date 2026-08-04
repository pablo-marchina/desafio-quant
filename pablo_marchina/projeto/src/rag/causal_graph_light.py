"""Causal graph light — lightweight causal graphs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CausalGraphLightConfig(BaseModel):
    causal_weight: float = 0.2


class CausalGraphLight:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CausalGraphLightConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        causal_words = {"because", "since", "therefore", "hence", "thus", "so", "cause", "effect", "lead", "result"}
        for ctx in contexts:
            words = set(ctx.content.lower().split())

            causal_count = len(words & causal_words)

            causal_score = min(1.0, causal_count * 0.1)

            ctx.relevance_score = round(
                (1.0 - self.cfg.causal_weight) * ctx.relevance_score + self.cfg.causal_weight * causal_score,
                4,
            )

        return contexts
