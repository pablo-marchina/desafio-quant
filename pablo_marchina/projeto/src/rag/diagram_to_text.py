from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_DIAGRAM_REF = re.compile(r"\b(diagram|figure|graph|chart|plot|schematic|flowchart)\b", re.I)
_ALT_TEXT = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_CAPTION = re.compile(r"<(fig|caption|figure)>([^<]+)</\1>", re.I)


class DiagramToText:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            refs = _DIAGRAM_REF.findall(ctx.content)
            alts = _ALT_TEXT.findall(ctx.content)
            captions = _CAPTION.findall(ctx.content)
            if refs or alts or captions:
                ctx.content = f"[diagrams:{len(refs)} alt_texts:{len(alts)} captions:{len(captions)}]\n{ctx.content}"
        return contexts
