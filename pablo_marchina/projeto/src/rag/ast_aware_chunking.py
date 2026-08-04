from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_CODE_BLOCK = re.compile(r"(```[\s\S]*?```|`[^`]+`|(?:^|\n)(?: {4}.*\n)+)", re.MULTILINE)
_FUNC_DEF = re.compile(r"\b(def |class |fn |func |function )", re.MULTILINE)


class AstAwareChunking:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            code_blocks = _CODE_BLOCK.findall(ctx.content)
            symbols = _FUNC_DEF.findall(ctx.content)
            if code_blocks:
                ctx.content = f"[code_blocks:{len(code_blocks)} symbols:{len(symbols)}]\n{ctx.content}"
        return contexts
