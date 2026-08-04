from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_BOILER_KEYWORDS = re.compile(
    r"\b(copyright|all rights reserved|terms|privacy|cookie|"
    r"disclaimer|legal|subscribe|newsletter|advertisement|sponsored|"
    r"comment|share|tweet|facebook|instagram|twitter|linkedin)\b",
    re.I,
)
_SHORT_LINES = re.compile(r"^.{1,30}$", re.MULTILINE)
_LINK_LINES = re.compile(r"^\[.*?\]\(.*?\)$", re.MULTILINE)


class BoilerpipeStyleExtraction:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            lines = ctx.content.split("\n")
            bp_hits = sum(1 for _l in lines if _BOILER_KEYWORDS.search(_l))
            short = sum(1 for _l in lines if _SHORT_LINES.match(_l) and _l.strip())
            links = sum(1 for _l in lines if _LINK_LINES.match(_l))
            content_lines = len(lines) - (bp_hits + short + links)
            ctx.content = f"[boilerpipe:boilerplate={bp_hits} short={short} links={links} content_lines={content_lines}]\n{ctx.content}"
        return contexts
