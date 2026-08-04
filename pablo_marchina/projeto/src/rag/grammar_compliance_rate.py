from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_JSON_OBJECT = re.compile(r"^\{.*\}$", re.DOTALL)
_JSON_ARRAY = re.compile(r"^\[.*\]$", re.DOTALL)
_XML_TAG = re.compile(r"^<(\w+)>.*</\1>$", re.DOTALL)


class GrammarComplianceRate:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        grammar_type = kwargs.get("grammar_type", "json")
        for ctx in contexts:
            c = ctx.content.strip()
            if grammar_type == "json":
                compliant = bool(_JSON_OBJECT.match(c) or _JSON_ARRAY.match(c))
            elif grammar_type == "xml":
                compliant = bool(_XML_TAG.match(c))
            else:
                compliant = True
            ctx.content = f"[compliance:{1.0 if compliant else 0.0}]\n{ctx.content}"
        return contexts
