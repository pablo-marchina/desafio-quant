from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_SS_REF = re.compile(r"\b(screenshot|screen.?shot|capture|print.?screen)\b", re.I)
_IMG_REF = re.compile(r"!\[.*?\]\(.*?\)", re.I)


class ScreenshotToStructuredData:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            ss_refs = _SS_REF.findall(ctx.content)
            imgs = _IMG_REF.findall(ctx.content)
            if ss_refs or imgs:
                ctx.content = f"[screenshots:{len(ss_refs)} images:{len(imgs)}]\n{ctx.content}"
        return contexts
