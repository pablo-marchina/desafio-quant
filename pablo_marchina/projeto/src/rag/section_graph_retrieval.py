from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_SECTION_RE = re.compile(r"(?:^|\n)(#{1,6}\s+.*?)(?=\n#{1,6}\s+|\Z)", re.DOTALL)


class SectionGraphRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = str(kwargs.get("query", "")).lower()
        for ctx in contexts:
            sections = _SECTION_RE.findall(ctx.content)
            if sections:
                scored = []
                for sec in sections:
                    heading = sec.split("\n")[0]
                    score = sum(1 for w in query.split() if w in heading.lower())
                    scored.append((score, sec))
                scored.sort(key=lambda x: -x[0])
                ctx.content = "\n\n".join(s for _, s in scored)
        return contexts
