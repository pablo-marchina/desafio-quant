"""Quote-first packing — pack quotes first."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class QuoteFirstPackingConfig(BaseModel):
    max_quotes: int = 5


class QuoteFirstPacking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = QuoteFirstPackingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        with_quotes = []
        without_quotes = []
        for ctx in contexts:
            quotes = re.findall(r'"([^"]*)"', ctx.content)
            if quotes:
                quote_score = min(0.3, len(quotes) * 0.05)
                ctx.relevance_score = round(min(1.0, ctx.relevance_score + quote_score), 4)
                with_quotes.append(ctx)
            else:
                without_quotes.append(ctx)
        with_quotes.sort(key=lambda c: c.relevance_score, reverse=True)
        without_quotes.sort(key=lambda c: c.relevance_score, reverse=True)
        return (with_quotes[: self.cfg.max_quotes] + without_quotes)[: self.cfg.max_quotes * 2]
