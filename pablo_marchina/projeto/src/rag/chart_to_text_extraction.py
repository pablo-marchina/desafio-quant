from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_CHART_DATA = re.compile(r"\b(\d+[\d,.]*%?)\s*[\(\[]?\s*(\d{4}|\w+)\s*[\)\]]?")
_CHART_REF = re.compile(r"\b(chart|figure|graph)\s+\d+\b", re.I)


class ChartToTextExtraction:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            data_points = _CHART_DATA.findall(ctx.content)
            refs = _CHART_REF.findall(ctx.content)
            if data_points or refs:
                ctx.content = f"[chart_data:{len(data_points)} refs:{len(refs)}]\n{ctx.content}"
        return contexts
