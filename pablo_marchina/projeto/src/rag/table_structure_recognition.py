from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_SEP_ROW = re.compile(r"^\|[-:| ]+\|$", re.MULTILINE)


class TableStructureRecognition:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            rows = _TABLE_ROW.findall(ctx.content)
            if rows:
                has_header = bool(_SEP_ROW.search(ctx.content))
                body_rows = len(rows) - (2 if has_header else 0)
                ctx.content = "[table_structure:header={} rows={}]\n{}".format(
                    "yes" if has_header else "no", max(0, body_rows), ctx.content
                )
        return contexts
