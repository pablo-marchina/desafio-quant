from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_OVERUSE_SIGNALS = [
    re.compile(r"(called|invoked|used)\s+(the\s+)?(tool|function|API)\s+\d+", re.IGNORECASE),
    re.compile(r"unnecessary\s+(call|invocation|request)", re.IGNORECASE),
    re.compile(r"redundant\s+(call|check|request)", re.IGNORECASE),
    re.compile(r"(call|query|request)\s+(again|repeatedly)", re.IGNORECASE),
    re.compile(r"multiple\s+(calls|queries|requests)", re.IGNORECASE),
    re.compile(r"excessive\s+(calls?|queries?|requests?)", re.IGNORECASE),
    re.compile(r"spam|flood", re.IGNORECASE),
]


class ToolOveruseRisk:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("overuse_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _OVERUSE_SIGNALS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.25), 4)

        return contexts
