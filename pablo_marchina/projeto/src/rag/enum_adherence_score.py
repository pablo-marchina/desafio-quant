from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class EnumAdherenceScore:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        enum_values = set(kwargs.get("enum_values", []))
        field = kwargs.get("field", "")
        for ctx in contexts:
            if not enum_values:
                continue
            pattern = re.compile(rf'["\']?{field}["\']?\s*[:=]\s*["\']?([^"\'}}\n,]+)')
            match = pattern.search(ctx.content)
            if match:
                value = match.group(1).strip()
                adheres = 1.0 if value in enum_values else 0.0
                ctx.content = f"[enum_adherence:{adheres}]\n{ctx.content}"
        return contexts
