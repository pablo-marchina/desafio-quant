from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_INJECTION_SIGNALS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|below)\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|above|below)", re.IGNORECASE),
    re.compile(r"system\s+(prompt|instruction|message)", re.IGNORECASE),
    re.compile(r"You\s+are\s+(now|not\s+an?\s+AI|a\s+free\s+AI)", re.IGNORECASE),
    re.compile(r"role[-\s]?play\s+as", re.IGNORECASE),
    re.compile(r"do\s+not\s+(follow|obey|listen)", re.IGNORECASE),
    re.compile(r"output\s+(only|just|exactly)\s+this", re.IGNORECASE),
    re.compile(r"##\s*(system|user|assistant)\s*##", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"bypass|jailbreak|DAN|do.anything.now", re.IGNORECASE),
    re.compile(r"pretend\s+(to\s+be|you\s+are|that\s+you)", re.IGNORECASE),
    re.compile(r"new\s+rule", re.IGNORECASE),
    re.compile(r"override", re.IGNORECASE),
]


class PromptInjectionClassifierLocal:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("injection_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            signals_hit = self._classify(ctx.content)

            if len(signals_hit) >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.5), 4)

        return contexts

    def _classify(self, content: str) -> list[str]:
        hits: list[str] = []
        for pattern in _INJECTION_SIGNALS:
            if pattern.search(content):
                hits.append(pattern.pattern)
        return hits
