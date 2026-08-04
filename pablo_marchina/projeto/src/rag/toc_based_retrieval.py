from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TOC_LINE = re.compile(r"^[\d.]+\s+.{4,80}\.+\d+\s*$", re.MULTILINE)


class TocBasedRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = str(kwargs.get("query", "")).lower()
        for ctx in contexts:
            toc_entries = _TOC_LINE.findall(ctx.content)
            if toc_entries:
                matched = [e for e in toc_entries if any(w in e.lower() for w in query.split())]
                ctx.content = f"[toc_matched:{len(matched)}]\n{ctx.content}"
        return contexts
