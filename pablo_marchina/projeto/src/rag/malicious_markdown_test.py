from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_MALICIOUS_MD_PATTERNS = [
    re.compile(r"\[.*?\]\(.*?\)", re.IGNORECASE),
    re.compile(r"!\[.*?\]\(.*?\)", re.IGNORECASE),
    re.compile(r"<img[^>]*src\s*=", re.IGNORECASE),
    re.compile(r"<a[^>]*href\s*=", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*image", re.IGNORECASE),
    re.compile(r"onmouseover\s*=", re.IGNORECASE),
    re.compile(r"onclick\s*=", re.IGNORECASE),
    re.compile(r"```\s*script", re.IGNORECASE),
    re.compile(r"<[^>]*\s+style\s*=", re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.IGNORECASE | re.DOTALL),
    re.compile(r"#+.*?http[s]?://", re.IGNORECASE),
    re.compile(r"\[\^.*?\]:\s*http", re.IGNORECASE),
]


class MaliciousMarkdownTest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("malicious_threshold", 3))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _MALICIOUS_MD_PATTERNS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.3), 4)

        return contexts
