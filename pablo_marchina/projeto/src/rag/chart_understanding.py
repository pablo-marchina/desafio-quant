from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_CHART_KEYWORDS = re.compile(
    r"\b(bar\s?chart|line\s?chart|pie\s?chart|scatter\s?plot|histogram|"
    r"barchart|linechart|piechart|axis|legend|x-?axis|y-?axis|data\s?point)\b",
    re.I,
)


class ChartUnderstanding:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            chart_terms = _CHART_KEYWORDS.findall(ctx.content)
            if chart_terms:
                ctx.content = f"[chart_terms:{len(chart_terms)}]\n{ctx.content}"
        return contexts
