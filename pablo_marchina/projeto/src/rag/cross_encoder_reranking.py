from __future__ import annotations

import math
import re
from typing import Any

from src.rag.schemas import RetrievedContext


class CrossEncoderReranking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    @staticmethod
    def _token_overlap(query_tokens: set[str], text: str) -> float:
        text_tokens = set(re.findall(r"\w+", text.lower()))
        if not query_tokens or not text_tokens:
            return 0.0
        return len(query_tokens & text_tokens) / math.sqrt(len(query_tokens) * len(text_tokens))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = str(kwargs.get("query", ""))
        query_tokens = set(re.findall(r"\w+", query.lower()))
        for ctx in contexts:
            overlap = self._token_overlap(query_tokens, ctx.content)
            ctx.relevance_score = round(ctx.relevance_score + overlap * 0.5, 4)
        return sorted(contexts, key=lambda c: -c.relevance_score)
