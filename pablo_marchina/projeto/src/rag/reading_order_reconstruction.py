from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_COLUMN_SEP = re.compile(r" {4,}")
_FLOAT_RE = re.compile(r"\b(tab|col|fig|footer|header)\b", re.I)


class ReadingOrderReconstruction:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            lines = ctx.content.split("\n")
            ordered: list[str] = []
            for line in lines:
                cols = _COLUMN_SEP.split(line)
                ordered.extend(c.strip() for c in cols if c.strip())
            ctx.content = "\n".join(ordered)
        return contexts
