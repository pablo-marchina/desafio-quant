from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_HEADING_RE = re.compile(r"^(#{1,6}\s+|(?:^|\n)(?:\d+\.\s*)+[A-Z])", re.MULTILINE)
_LIST_RE = re.compile(r"^(\s*[-*+]\s|\s*\d+[.)]\s)", re.MULTILINE)


class PDFLayoutParser:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            headings = _HEADING_RE.findall(ctx.content)
            lists = _LIST_RE.findall(ctx.content)
            layout_info = {
                "headings": len(headings),
                "lists": len(lists),
                "paragraphs": len(re.findall(r"\n\n+", ctx.content)) + 1,
            }
            ctx.content = f"[layout:headings={layout_info['headings']} lists={layout_info['lists']} paras={layout_info['paragraphs']}]\n{ctx.content}"
        return contexts
