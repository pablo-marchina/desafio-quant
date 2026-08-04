from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_SECTION_BREAK = re.compile(r"\n(#{1,6}\s+.*?\n|={3,}\n|_{3,}\n)")


class LayoutAwareChunking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            parts = _SECTION_BREAK.split(ctx.content)
            if len(parts) > 1:
                ctx.content = "\n".join(parts)
        return contexts
