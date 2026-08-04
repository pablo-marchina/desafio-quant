from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_RULE_LINE = re.compile(r"^(\w+)\s*->\s*(.+)$", re.MULTILINE)


class CfgConstrainedDecoding:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        grammar = kwargs.get("grammar", "")
        rules = _RULE_LINE.findall(grammar)
        for ctx in contexts:
            if rules:
                symbols_found = sum(
                    1 for lhs, rhs in rules if lhs in ctx.content or any(t in ctx.content for t in rhs.split())
                )
                ctx.content = f"[cfg:symbols={len(rules)} matched={symbols_found}]\n{ctx.content}"
        return contexts
