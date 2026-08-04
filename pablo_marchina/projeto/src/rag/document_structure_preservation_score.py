from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_STRUCTURE_MARKERS = [
    (re.compile(r"\[layout:"), "layout"),
    (re.compile(r"\[table:"), "table"),
    (re.compile(r"\[tree:"), "tree"),
    (re.compile(r"#{1,6}\s+"), "heading"),
    (re.compile(r"\[code_blocks:"), "code"),
    (re.compile(r"\[diagrams:"), "diagram"),
]


class DocumentStructurePreservationScore:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            found = sum(1 for pat, _ in _STRUCTURE_MARKERS if pat.search(ctx.content))
            score = round(found / len(_STRUCTURE_MARKERS), 4)
            ctx.content = f"[struct_score:{score}]\n{ctx.content}"
        return contexts
