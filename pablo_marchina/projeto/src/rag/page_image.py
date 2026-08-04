from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_PAGE_MARKERS = re.compile(
    r"\b(page\s*\d+|p\.?\s*\d+|pg\s*\d+|page\s+break|" r"page\s+number|page\s+footer|page\s+header)\b",
    re.I,
)


class PageImageAnalyzer:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            markers = _PAGE_MARKERS.findall(ctx.content)
            if markers:
                ctx.content = (
                    f"[page_markers:{';'.join(set(m.lower().replace(' ', '_') for m in markers))}]\n{ctx.content}"
                )
        return contexts
