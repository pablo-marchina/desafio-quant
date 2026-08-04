from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_GrammarPatterns = {
    "json": re.compile(r"^\{.*\}$", re.DOTALL),
    "xml": re.compile(r"^<\w+>.*</\w+>$", re.DOTALL),
    "number": re.compile(r"^-?\d+(\.\d+)?$"),
    "bool": re.compile(r"^(true|false|True|False|0|1)$"),
}


class GrammarConstrainedEditing:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        target_type = kwargs.get("target_type", "json")
        pattern = _GrammarPatterns.get(target_type)
        for ctx in contexts:
            if pattern:
                compliant = bool(pattern.fullmatch(ctx.content.strip()))
                ctx.content = f"[edited:{target_type} compliant={compliant}]\n{ctx.content}"
        return contexts
