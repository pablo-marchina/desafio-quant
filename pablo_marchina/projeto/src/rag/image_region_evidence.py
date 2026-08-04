from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_REGION_REF = re.compile(
    r"\b(region|area|section|portion|quadrant|top|bottom|left|right|upper|lower)\s+(?:of\s+)?(?:the\s+)?(?:image|figure|photo|picture)\b",
    re.I,
)
_BBOX = re.compile(r"\[(\d+),(\d+),(\d+),(\d+)\]")


class ImageRegionEvidence:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            regions = _REGION_REF.findall(ctx.content)
            bboxes = _BBOX.findall(ctx.content)
            if regions or bboxes:
                ctx.content = f"[regions:{len(regions)} bboxes:{len(bboxes)}]\n{ctx.content}"
        return contexts
