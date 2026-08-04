from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_CAPTION_RE = re.compile(r"<(fig|caption|figure)>([^<]+)</\1>", re.I)


class ImageDescriptionEnrichment:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            images = _IMG_RE.findall(ctx.content)
            captions = {m[1].strip().lower() for m in _CAPTION_RE.findall(ctx.content)}
            enriched = ctx.content
            for alt_text, url in images:
                if alt_text:
                    enriched = enriched.replace(f"![{alt_text}]({url})", f"![{alt_text}]({url}) [desc:{alt_text}]", 1)
                elif url.lower() in captions:
                    pass
            ctx.content = enriched
        return contexts
