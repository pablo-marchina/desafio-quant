from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_ELEMENT_TYPES = {
    "title": re.compile(r"^#\s+\S", re.MULTILINE),
    "heading": re.compile(r"^#{2,6}\s+\S", re.MULTILINE),
    "table": re.compile(r"^\|.+\|$", re.MULTILINE),
    "list": re.compile(r"^\s*[-*+]\s", re.MULTILINE),
    "code": re.compile(r"```[\s\S]*?```", re.MULTILINE),
    "quote": re.compile(r"^>\s", re.MULTILINE),
}


class UnstructuredOss:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            elements = {k: len(v.findall(ctx.content)) for k, v in _ELEMENT_TYPES.items()}
            total = sum(elements.values())
            el_info = " ".join(f"{k}={v}" for k, v in elements.items() if v > 0)
            ctx.content = f"[unstructured:elements={total} {el_info}]\n{ctx.content}"
        return contexts
