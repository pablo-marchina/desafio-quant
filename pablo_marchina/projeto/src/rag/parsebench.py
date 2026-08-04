from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_STRUCTURE_SCORE = re.compile(r"\[(layout:|table:|tree:|code_blocks:|diagrams:|struct_score:)")
_PARSE_ERRORS = re.compile(r"[\\]{3,}|�|[\x00-\x08\x0b\x0c\x0e-\x1f]")


class Parsebench:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            struct_hits = len(_STRUCTURE_SCORE.findall(ctx.content))
            errors = len(_PARSE_ERRORS.findall(ctx.content))
            parse_score = round(min((struct_hits * 0.2) - (errors * 0.1), 1.0), 4)
            ctx.content = f"[parsebench:score={parse_score} structures={struct_hits} errors={errors}]\n{ctx.content}"
        return contexts
