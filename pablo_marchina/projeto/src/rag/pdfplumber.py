from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TABLE_DETECT = re.compile(r"^\|.+\|$", re.MULTILINE)
_TEXT_BLOCK = re.compile(r"\n\n+")
_NUMBERED_LIST = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


class Pdfplumber:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            tables = len(_TABLE_DETECT.findall(ctx.content))
            blocks = len(_TEXT_BLOCK.split(ctx.content))
            lists = len(_NUMBERED_LIST.findall(ctx.content))
            ctx.content = f"[pdfplumber:tables={tables} blocks={blocks} lists={lists}]\n{ctx.content}"
        return contexts
