from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_FALLBACK_SIGNALS = [
    re.compile(r"(missing|absent|unavailable)\s+(fallback|backup|alternative)", re.IGNORECASE),
    re.compile(r"no\s+fallback", re.IGNORECASE),
    re.compile(r"fallback\s+(not|never|not\s+configured)", re.IGNORECASE),
    re.compile(r"requires?\s+(a\s+)?fallback", re.IGNORECASE),
    re.compile(r"must\s+have\s+fallback", re.IGNORECASE),
    re.compile(r"without\s+(a\s+)?(backup|alternative|fallback)", re.IGNORECASE),
    re.compile(r"fallback\s+(recommended|required|mandatory)", re.IGNORECASE),
]


class FallbackRequiredGate:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if self._needs_fallback(ctx):
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.15), 4)

        return contexts

    def _needs_fallback(self, ctx: RetrievedContext) -> bool:
        return any(p.search(ctx.content) for p in _FALLBACK_SIGNALS)
