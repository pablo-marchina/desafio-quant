from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TABLE_LINE = re.compile(r"^\|.*\|$", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_COL_SEP = re.compile(r"\|")


class TableAwareChunking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            rows = _TABLE_ROW.findall(ctx.content)
            if rows:
                col_counts = [len(_COL_SEP.findall(r)) - 1 for r in rows]
                ctx.content = f"[table:{len(rows)}rows {max(col_counts) if col_counts else 0}cols]\n{ctx.content}"
        return contexts
