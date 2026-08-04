from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_SOURCE_POISON_SIGNALS = [
    re.compile(r"\.(xyz|tk|ml|ga|cf|click|download|free)\b", re.IGNORECASE),
    re.compile(r"sponsored|paid\s+post|advertisement", re.IGNORECASE),
    re.compile(r"guest\s+post|submit\s+(article|content)", re.IGNORECASE),
    re.compile(r"buy\s+(followers|likes|views|traffic)", re.IGNORECASE),
    re.compile(r"click\s+(here|now|this\s+link)", re.IGNORECASE),
    re.compile(r"sign\s+up\s+(now|today)", re.IGNORECASE),
    re.compile(r"limited\s+(time\s+)?offer", re.IGNORECASE),
    re.compile(r"you'?ve?\s+won", re.IGNORECASE),
    re.compile(r"congratulations?\s+(you|winner)", re.IGNORECASE),
]


class SourcePoisoningTests:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("poison_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _SOURCE_POISON_SIGNALS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.35), 4)

        return contexts
