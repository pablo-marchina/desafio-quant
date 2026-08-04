from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TOOL_MISUSE_PATTERNS = [
    re.compile(r"call\s+(the\s+)?(API|tool|function)\s+without", re.IGNORECASE),
    re.compile(r"repeated\s+(call|request)", re.IGNORECASE),
    re.compile(r"infinite\s+loop", re.IGNORECASE),
    re.compile(r"recursive\s+(call|invocation)", re.IGNORECASE),
    re.compile(r"tool\s+not\s+found", re.IGNORECASE),
    re.compile(r"invalid\s+(argument|parameter|input)", re.IGNORECASE),
    re.compile(r"error\s+code\s+\d{3}", re.IGNORECASE),
    re.compile(r"timeout|timed\s+out", re.IGNORECASE),
    re.compile(r"rate\s+limit|too\s+many\s+requests", re.IGNORECASE),
]


class ToolMisuseTests:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("misuse_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _TOOL_MISUSE_PATTERNS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.3), 4)

        return contexts
