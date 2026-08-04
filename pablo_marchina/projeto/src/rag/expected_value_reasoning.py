from __future__ import annotations

import math
from typing import Any

from src.rag.schemas import RetrievedContext


class ExpectedValueReasoning:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            probability = ctx.relevance_score

            token_count = len(ctx.content.split())

            utility = math.log(token_count + 1) / 10.0

            url_quality = 0.2 if ctx.url else 0.0

            ev = probability * min(utility + url_quality, 1.0)

            ctx.relevance_score = round(max(0.0, min(1.0, ev)), 4)

            contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        return contexts
