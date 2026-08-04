from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_INJECTION_EMBEDDED = [
    re.compile(r"ignore\s+(all\s+)?prior", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+(your\s+)?(guidelines?|instructions?)", re.IGNORECASE),
    re.compile(r"this\s+is\s+(an?\s+)?(order|command|instruction)", re.IGNORECASE),
    re.compile(r"you\s+will\s+obey", re.IGNORECASE),
    re.compile(r"must\s+respond\s+with", re.IGNORECASE),
    re.compile(r"if\s+you\s+(see|read|understand)", re.IGNORECASE),
    re.compile(r"say\s+(the\s+)?(word|phrase)", re.IGNORECASE),
    re.compile(r"output\s+the\s+following", re.IGNORECASE),
    re.compile(r"hidden\s+(instruction|command|text)", re.IGNORECASE),
    re.compile(r"invisible\s+(text|instruction)", re.IGNORECASE),
]


class IndirectPromptInjectionThroughRetrievedDocs:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("injection_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _INJECTION_EMBEDDED if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.5), 4)

        return contexts
