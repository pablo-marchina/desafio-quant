from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class HeadingPathRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = str(kwargs.get("query", "")).lower()
        for ctx in contexts:
            headings = _HEADING_RE.findall(ctx.content)
            if headings:
                path = " > ".join(h[1] for h in headings)
                path_score = sum(1 for w in query.split() if w in path.lower())
                if path_score > 0:
                    ctx.relevance_score = round(ctx.relevance_score + min(path_score * 0.1, 0.3), 4)
        return contexts
