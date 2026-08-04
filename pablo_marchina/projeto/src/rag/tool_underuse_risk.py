from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_UNDERUSE_SIGNALS = [
    re.compile(r"should\s+have\s+(called|used|invoked)", re.IGNORECASE),
    re.compile(r"missed\s+(opportunity|calling|using)", re.IGNORECASE),
    re.compile(r"could\s+have\s+(used|called|queried)", re.IGNORECASE),
    re.compile(r"did\s+not\s+(use|call|invoke|query)", re.IGNORECASE),
    re.compile(r"insufficient\s+(tool|function|API)\s+usage", re.IGNORECASE),
    re.compile(r"manual\s+(lookup|search|check)", re.IGNORECASE),
    re.compile(r"tool\s+available\s+but\s+not\s+used", re.IGNORECASE),
    re.compile(r"skipped\s+(calling|using|invoking)", re.IGNORECASE),
]


class ToolUnderuseRisk:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("underuse_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _UNDERUSE_SIGNALS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.2), 4)

        return contexts
