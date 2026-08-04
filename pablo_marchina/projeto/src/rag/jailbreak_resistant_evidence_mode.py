from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_JAILBREAK_PATTERNS = [
    re.compile(r"DAN|do.anything.now|jailbroken|jailbreak", re.IGNORECASE),
    re.compile(r"You\s+are\s+now\s+DAN", re.IGNORECASE),
    re.compile(r"hypothetical\s+(scenario|response)", re.IGNORECASE),
    re.compile(r"character\s+play|role.play", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+are", re.IGNORECASE),
    re.compile(r"no\s+(rules|restrictions|boundaries|limits)", re.IGNORECASE),
    re.compile(r"unfiltered|uncensored|unconstrained", re.IGNORECASE),
    re.compile(r"remove\s+(all\s+)?(safety|guardrails)", re.IGNORECASE),
    re.compile(r"this\s+is\s+(a\s+)?(hypothetical|fiction|movie|game)", re.IGNORECASE),
    re.compile(r"you\s+must\s+(respond|answer|reply)\s+to", re.IGNORECASE),
]


class JailbreakResistantEvidenceMode:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("jailbreak_threshold", 1))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            matches = sum(1 for p in _JAILBREAK_PATTERNS if p.search(ctx.content))

            if matches >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.6), 4)

        return contexts
