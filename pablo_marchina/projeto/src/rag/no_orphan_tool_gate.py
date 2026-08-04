from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_ORPHAN_SIGNALS = [
    re.compile(r"(registered|declared|defined|created)\s+(tool|function)", re.IGNORECASE),
    re.compile(r"(never|not)\s+(called|invoked|used|referenced)", re.IGNORECASE),
    re.compile(r"unused\s+(tool|function|method)", re.IGNORECASE),
    re.compile(r"orphan\s+(tool|function)", re.IGNORECASE),
    re.compile(r"(dead|zombie|stale)\s+(code|function|tool)", re.IGNORECASE),
    re.compile(r"no\s+(caller|consumer|user)", re.IGNORECASE),
    re.compile(r"unreferenced", re.IGNORECASE),
]


class NoOrphanToolGate:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if self._is_orphan_related(ctx):
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.2), 4)

        return contexts

    def _is_orphan_related(self, ctx: RetrievedContext) -> bool:
        return any(p.search(ctx.content) for p in _ORPHAN_SIGNALS)
