from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_BOILERPLATE = re.compile(
    r"\b(copyright|all rights reserved|terms of service|privacy policy|"
    r"cookie|cookie policy|disclaimer|legal notice|subscribe|newsletter|"
    r"share this|related articles|comments|advertisement|sponsored)\b",
    re.I,
)
_NAV_TEXT = re.compile(r"^\s*(home|next|previous|back|top|menu|search|login|sign.?up|logout)\s*$", re.I | re.MULTILINE)


class Trafilatura:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            lines = ctx.content.split("\n")
            cleaned = [line for line in lines if not _NAV_TEXT.match(line)]
            bp_count = len(_BOILERPLATE.findall(ctx.content))
            main_content = "\n".join(cleaned)
            main_text_ratio = round(len(main_content) / max(len(ctx.content), 1), 4) if ctx.content else 0.0
            ctx.content = f"[trafilatura:boilerplate={bp_count} main_ratio={main_text_ratio}]\n{main_content}"
        return contexts
