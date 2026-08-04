from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_VISUAL_FEATURES = re.compile(
    r"\b(layout|column|margin|header|footer|page.?break|" r"watermark|stamp|logo|signature|barcode|qr.?code)\b",
    re.I,
)


class VisualDocumentRetriever:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            features = _VISUAL_FEATURES.findall(ctx.content)
            if features:
                ctx.content = f"[visual_features:{';'.join(set(features))}]\n{ctx.content}"
        return contexts
