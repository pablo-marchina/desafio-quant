from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_EBNF_RULE = re.compile(r"^(\w+)\s*::=\s*(.+)$", re.MULTILINE)


class EbnfConstrainedDecoding:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        grammar = kwargs.get("grammar", "")
        rules = _EBNF_RULE.findall(grammar)
        for ctx in contexts:
            if rules:
                match_count = sum(1 for lhs, rhs in rules if lhs.lower() in ctx.content.lower())
                ctx.content = f"[ebnf:rules={len(rules)} matches={match_count}]\n{ctx.content}"
        return contexts
