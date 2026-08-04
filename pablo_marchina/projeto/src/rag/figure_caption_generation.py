from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_FIGURE_REF = re.compile(r"\b(fig(?:ure)?)\s*\.?\s*(\d+)\b", re.I)
_CAPTION = re.compile(
    r"(?:^|\n)(?:Fig(?:ure)?\s*\d+[.:]?\s*|[Ff]igure\s*\d+[.:]?\s*)(.+?)(?=\n\s*(?:Fig(?:ure)?|\Z|$))", re.DOTALL
)


class FigureCaptionGeneration:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            refs = _FIGURE_REF.findall(ctx.content)
            captions = _CAPTION.findall(ctx.content)
            if captions:
                ctx.content = (
                    f"[captions:{len(captions)}]\n" + "\n".join(c.strip() for c in captions) + "\n---\n" + ctx.content
                )
            elif refs:
                ctx.content = f"[figure_refs:{len(refs)}]\n{ctx.content}"
        return contexts
