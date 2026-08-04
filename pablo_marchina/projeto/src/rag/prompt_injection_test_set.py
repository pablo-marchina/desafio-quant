from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TEST_SIGNALS = [
    re.compile(r"test\s+injection", re.IGNORECASE),
    re.compile(r"simulated\s+attack", re.IGNORECASE),
    re.compile(r"red\s+team", re.IGNORECASE),
    re.compile(r"adversarial\s+example", re.IGNORECASE),
    re.compile(r"prompt\s+injection\s+sample", re.IGNORECASE),
    re.compile(r"jailbreak\s+(test|sample|example)", re.IGNORECASE),
    re.compile(r"security\s+test", re.IGNORECASE),
    re.compile(r"eval\s+dataset", re.IGNORECASE),
    re.compile(r"injection\s+attempt", re.IGNORECASE),
]


class PromptInjectionTestSet:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("test_threshold", 1))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _TEST_SIGNALS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.2), 4)

        return contexts
