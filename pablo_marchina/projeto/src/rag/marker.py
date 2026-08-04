from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_MARKER_PATTERNS = {
    "bullet": re.compile(r"^\s*[-*+]\s", re.MULTILINE),
    "numbered": re.compile(r"^\s*\d+[.)]\s", re.MULTILINE),
    "blockquote": re.compile(r"^>\s", re.MULTILINE),
    "hr": re.compile(r"^(?:---|\*\*\*|___)\s*$", re.MULTILINE),
}


class Marker:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            counts = {k: len(v.findall(ctx.content)) for k, v in _MARKER_PATTERNS.items()}
            marker_info = " ".join(f"{k}={v}" for k, v in counts.items() if v > 0)
            if marker_info:
                ctx.content = f"[marker:{marker_info}]\n{ctx.content}"
        return contexts
