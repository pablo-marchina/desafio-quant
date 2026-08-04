from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE_RE = re.compile(r"`([^`]+)`")


class Pymupdf4llm:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            headings = len(_HEADING_RE.findall(ctx.content))
            bold = len(_BOLD_RE.findall(ctx.content))
            italic = len(_ITALIC_RE.findall(ctx.content))
            code = len(_CODE_RE.findall(ctx.content))
            ctx.content = f"[pymupdf4llm:headings={headings} bold={bold} italic={italic} code={code}]\n{ctx.content}"
        return contexts
