from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_IMG_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_TABLE_RE = re.compile(r"^\|.+\|$", re.MULTILINE)
_MEDIA_REF = re.compile(r"\b(image|figure|table|chart|diagram|video|audio)\b", re.I)


class MultimodalIngestion:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            images = _IMG_RE.findall(ctx.content)
            tables = _TABLE_RE.findall(ctx.content)
            media = _MEDIA_REF.findall(ctx.content)
            types = []
            if images:
                types.append(f"images:{len(images)}")
            if tables:
                types.append(f"tables:{len(tables)}")
            if media:
                types.append(f"media:{len(media)}")
            if types:
                ctx.content = f"[multimodal:{';'.join(types)}]\n{ctx.content}"
        return contexts
