from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_FREE_LICENSES = [
    "mit",
    "apache 2.0",
    "apache-2.0",
    "bsd",
    "bsd-2",
    "bsd-3",
    "cc0",
    "cc by",
    "creative commons",
    "unlicense",
    "public domain",
    "lgpl",
    "lgpl-2.1",
    "lgpl-3.0",
    "mozilla",
    "mpl",
    "mpl-2.0",
    "isc",
]

_NON_FREE_SIGNALS = [
    re.compile(r"(commercial|proprietary|closed.source)\s+license", re.IGNORECASE),
    re.compile(r"all\s+rights\s+reserved", re.IGNORECASE),
    re.compile(r"not\s+for\s+(commercial|redistribution)", re.IGNORECASE),
    re.compile(r"requires\s+(a\s+)?(paid|purchased)\s+license", re.IGNORECASE),
    re.compile(r"license\s+required\s+for\s+(commercial|enterprise)", re.IGNORECASE),
    re.compile(r"royalty|royalties", re.IGNORECASE),
    re.compile(r"patent\s+license", re.IGNORECASE),
    re.compile(r"non[-\s]?free", re.IGNORECASE),
    re.compile(r"per[-\s]?(user|seat|device)\s+license", re.IGNORECASE),
]


class FreeOnlyLicenseGate:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if not self._is_compatible(ctx):
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.5), 4)

        return contexts

    def _is_compatible(self, ctx: RetrievedContext) -> bool:
        content_lower = ctx.content.lower()
        non_free_hit = any(p.search(content_lower) for p in _NON_FREE_SIGNALS)
        if non_free_hit:
            return False
        return True
