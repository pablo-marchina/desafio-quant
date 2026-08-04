from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_TABLE_MARKER = re.compile(r"\[table:\d+rows \d+cols\]")


class CrossPageTableMerging:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        table_groups: dict[str, list[RetrievedContext]] = {}
        for ctx in contexts:
            marker = _TABLE_MARKER.search(ctx.content)
            if marker and ctx.title:
                key = f"{ctx.source_id}:{ctx.title}"
                table_groups.setdefault(key, []).append(ctx)
        for group in table_groups.values():
            if len(group) > 1:
                merged_rows = []
                for g in group:
                    rows = _TABLE_ROW.findall(g.content)
                    merged_rows.extend(rows)
                if merged_rows:
                    group[0].content = "[merged:{}pages {}rows]\n{}".format(
                        len(group), len(merged_rows), "\n".join(merged_rows)
                    )
                    for g in group[1:]:
                        g.content = "[duplicate_merged]"
        return contexts
