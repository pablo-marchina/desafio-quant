from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_FIGURE_REF = re.compile(r"\b(?:fig|figure|illustration|diagram)\s*\.?\s*(\d+)\b", re.I)
_FIGURE_DESC = re.compile(r"(?:shows|illustrates|depicts|demonstrates|presents|displays)\s+(.+?)(?:\.|;|\n|$)", re.I)


class FigureGrounding:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            refs = _FIGURE_REF.findall(ctx.content)
            descs = _FIGURE_DESC.findall(ctx.content)
            if refs or descs:
                ctx.content = f"[figure_grounding:refs={len(refs)} descs={len(descs)}]\n{ctx.content}"
        return contexts
