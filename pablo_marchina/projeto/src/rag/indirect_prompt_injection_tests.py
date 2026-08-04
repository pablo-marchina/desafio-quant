from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_INDIRECT_INJECTION_PATTERNS = [
    re.compile(r"(ignore|disregard|forget)\s+(all\s+)?(prior|previous|above)", re.IGNORECASE),
    re.compile(r"now\s+you\s+(will|must|should)\s+", re.IGNORECASE),
    re.compile(r"from\s+now\s+on", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"updated\s+(instructions?|guidelines?|rules?)", re.IGNORECASE),
    re.compile(r"##\s*(instructions?|rules?|tldr)\s*:?", re.IGNORECASE),
    re.compile(r"the\s+user\s+says?\s*:", re.IGNORECASE),
    re.compile(r"ignore\s+previous", re.IGNORECASE),
    re.compile(r"this\s+document\s+contains\s+instructions?", re.IGNORECASE),
]


class IndirectPromptInjectionTests:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("test_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _INDIRECT_INJECTION_PATTERNS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.4), 4)

        return contexts
