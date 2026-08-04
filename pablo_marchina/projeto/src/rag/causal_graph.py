"""Causal graph — build causal graphs."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CausalGraphConfig(BaseModel):
    causal_boost: float = 0.1


class CausalGraph:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CausalGraphConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            cause_signals = len(
                re.findall(
                    r"\b(causes|leads to|results in|due to|because|therefore|hence|consequently|as a result|triggers)\b",
                    ctx.content.lower(),
                )
            )

            effect_signals = len(
                re.findall(r"\b(effect|impact|influence|affects|changes|produces|creates)\b", ctx.content.lower())
            )

            causal_density = min(1.0, (cause_signals + effect_signals) * 0.05)

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + causal_density * self.cfg.causal_boost), 4)

        return contexts
