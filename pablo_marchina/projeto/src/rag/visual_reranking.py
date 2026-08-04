from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_VISUAL_CONTENT = re.compile(r"\b(chart|figure|diagram|graph|image|photo|screenshot|drawing|plot|illustration)\b", re.I)
_IMG_MARKDOWN = re.compile(r"!\[.*?\]\(.*?\)")
_TABLE_MARKDOWN = re.compile(r"^\|.+\|$", re.MULTILINE)


class VisualReranking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            visual_refs = len(_VISUAL_CONTENT.findall(ctx.content))
            images = len(_IMG_MARKDOWN.findall(ctx.content))
            tables = len(_TABLE_MARKDOWN.findall(ctx.content))
            visual_score = round(min((visual_refs + images * 2 + tables) / 10.0, 1.0), 4)
            ctx.relevance_score = round(ctx.relevance_score + visual_score * 0.15, 4)
        return sorted(contexts, key=lambda c: -c.relevance_score)
