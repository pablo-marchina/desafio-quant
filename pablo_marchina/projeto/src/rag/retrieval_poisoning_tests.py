from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_RETRIEVAL_POISON_PATTERNS = [
    re.compile(r"http[s]?://(bit\.ly|tinyurl|short\.link|shorturl)", re.IGNORECASE),
    re.compile(r"clickbait|sensational|shocking|unbelievable", re.IGNORECASE),
    re.compile(r"100%\s+(guaranteed|free|safe)", re.IGNORECASE),
    re.compile(r"earn\s+\$\d+", re.IGNORECASE),
    re.compile(r"make\s+money\s+fast", re.IGNORECASE),
    re.compile(r"work\s+from\s+home", re.IGNORECASE),
    re.compile(r"miracle\s+(cure|treatment|solution)", re.IGNORECASE),
    re.compile(r"secret\s+(method|formula|system|trick)", re.IGNORECASE),
    re.compile(r"double\s+your\s+(money|income|investment)", re.IGNORECASE),
]


class RetrievalPoisoningTests:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("poison_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _RETRIEVAL_POISON_PATTERNS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.4), 4)

        return contexts
