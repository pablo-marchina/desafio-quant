from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TEMPLATE_PATTERN = re.compile(r"\{\{[^}]*\}\}|<\w+>[^<]*</\w+>|<[^>]+>")


class GrammarBasedOutput:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        pattern = kwargs.get("pattern", "")
        pat = re.compile(pattern) if pattern else None
        for ctx in contexts:
            if pat:
                valid = bool(pat.fullmatch(ctx.content.strip()))
                ctx.content = f"[grammar_valid:{valid}]\n{ctx.content}"
            else:
                templates = _TEMPLATE_PATTERN.findall(ctx.content)
                if templates:
                    ctx.content = f"[templates:{len(templates)}]\n{ctx.content}"
        return contexts
