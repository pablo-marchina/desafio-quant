from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class ConstrainedDecoding:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        schema = kwargs.get("schema", "")
        pattern = re.compile(schema) if schema else None
        for ctx in contexts:
            if pattern:
                matches = pattern.findall(ctx.content)
                ctx.content = f"[constrained:matches={len(matches)}]\n{ctx.content}"
        return contexts
