from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)


class TableCellProvenance:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            rows = _TABLE_ROW.findall(ctx.content)
            if rows:
                cells = []
                for r_idx, row in enumerate(rows):
                    cols = [c.strip() for c in row.split("|")[1:-1]]
                    for c_idx, val in enumerate(cols):
                        if val:
                            cells.append(f"r{r_idx}c{c_idx}")
                ctx.content = f"[cells:{','.join(cells)}]\n{ctx.content}"
        return contexts
