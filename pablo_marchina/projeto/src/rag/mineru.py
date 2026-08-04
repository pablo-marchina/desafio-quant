from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_MULTI_COL = re.compile(r"(?:\S+\s+){10,}\S+\s{4,}\S")  # heuristic: wide spacing
_FIGURE_REF = re.compile(r"\b(fig|figure|table|chart)\s*\d+\b", re.I)
_MATH_RE = re.compile(r"\$[^$]+\$|\\\([^)]+\\\)|\\\[[\s\S]*?\\\]")


class Mineru:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            multi_col = 1 if _MULTI_COL.search(ctx.content) else 0
            figures = len(_FIGURE_REF.findall(ctx.content))
            math = len(_MATH_RE.findall(ctx.content))
            ctx.content = f"[mineru:multicolumn={multi_col} figures={figures} math={math}]\n{ctx.content}"
        return contexts
