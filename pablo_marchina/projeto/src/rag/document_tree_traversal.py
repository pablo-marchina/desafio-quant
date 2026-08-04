from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class DocumentTreeTraversal:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            headings = _HEADING_RE.findall(ctx.content)
            if headings:
                depth = min(len(h[0]) for h in headings)
                tree_parts = [f"{'  ' * (len(h[0]) - depth)}- {h[1]}" for h in headings]
                ctx.content = f"[tree:{'; '.join(tree_parts)}]\n{ctx.content}"
        return contexts
