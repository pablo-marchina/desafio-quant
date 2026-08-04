from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_LAYOUT_FEATURES = re.compile(r"\[layout:[^\]]+\]")


class LayoutGroundedQa:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = str(kwargs.get("query", "")).lower()
        for ctx in contexts:
            match = _LAYOUT_FEATURES.search(ctx.content)
            if match:
                ctx.content = f"[layout_features:{match.group()}]\n{_LAYOUT_FEATURES.sub('', ctx.content).strip()}"
                if query:
                    q_words = set(query.split())
                    c_words = set(ctx.content.lower().split())
                    overlap = len(q_words & c_words) / max(len(q_words), 1)
                    ctx.relevance_score = round(ctx.relevance_score + min(overlap, 0.5), 4)
        return contexts
