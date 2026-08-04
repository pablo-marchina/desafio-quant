"""Long-context verification pass — verification pass on long context."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LongContextVerificationPassConfig(BaseModel):
    verification_bonus: float = 0.1


class LongContextVerificationPass:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LongContextVerificationPassConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            factual_markers = len(
                re.findall(r"\b(according to|as stated|per|refer to|see|source|reference)\b", ctx.content.lower())
            )

            verification_score = min(0.3, factual_markers * 0.03)

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + verification_score), 4)

        return contexts
