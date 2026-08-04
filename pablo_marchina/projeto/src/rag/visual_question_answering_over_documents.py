from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_IMG_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_VISUAL_KEYWORDS = re.compile(r"\b(figure|chart|graph|diagram|plot|image|screenshot|photo|drawing)\b", re.I)


class VisualQuestionAnsweringOverDocuments:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = str(kwargs.get("query", "")).lower()
        for ctx in contexts:
            images = _IMG_RE.findall(ctx.content)
            vis_words = _VISUAL_KEYWORDS.findall(ctx.content)
            has_visual_content = bool(images) or bool(vis_words)
            q_visual = any(w in query for w in ["figure", "chart", "image", "diagram", "visual", "screenshot"])
            if q_visual and has_visual_content:
                ctx.relevance_score = round(min(ctx.relevance_score + 0.2, 1.0), 4)
            ctx.content = f"[vqa:visual={'yes' if has_visual_content else 'no'}]\n{ctx.content}"
        return contexts
