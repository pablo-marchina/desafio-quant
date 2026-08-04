from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_KEY_VALUE_PAIR = re.compile(r'["\']?(\w+)["\']?\s*[:=]\s*["\']?([^"\'}\n,]+)')
_STRUCT_MARKER = re.compile(r"\[(?:schema_preserved|compliance|grammar_valid|edited|cfg|ebnf):")


class StructuredOutputSemanticQuality:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            kv_pairs = _KEY_VALUE_PAIR.findall(ctx.content)
            struct_present = bool(_STRUCT_MARKER.search(ctx.content))
            quality = round(min(len(kv_pairs) / 10.0, 1.0), 4) if kv_pairs else (0.5 if struct_present else 0.0)
            ctx.content = f"[semantic_quality:{quality}]\n{ctx.content}"
        return contexts
