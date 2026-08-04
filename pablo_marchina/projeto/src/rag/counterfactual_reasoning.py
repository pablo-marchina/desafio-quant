"""Counterfactual reasoning — reason about counterfactuals in contexts."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CounterfactualReasoningConfig(BaseModel):
    counterfactual_boost: float = 0.1


class CounterfactualReasoning:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CounterfactualReasoningConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            cf_signals = len(
                re.findall(
                    r"(?:if |would|could|should|might|may|alternatively|otherwise|assuming|suppose)",
                    ctx.content.lower(),
                )
            )

            boost = min(0.2, cf_signals * 0.02) * self.cfg.counterfactual_boost

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + boost), 4)

        return contexts
