from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)


class TableToTextSerializationBenchmark:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            rows = _TABLE_ROW.findall(ctx.content)
            if rows:
                density = sum(len(r) for r in rows) / max(len(rows), 1)
                serialization_score = round(min(density / 80.0, 1.0), 4)
                ctx.content = f"[serialization_score:{serialization_score}]\n{ctx.content}"
        return contexts
