from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_SCHEMA_KEY_RE = re.compile(r'"(\w+)"\s*:')


class SchemaPreservingRevision:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        schema = kwargs.get("schema", {})
        expected_keys = set(schema.keys()) if isinstance(schema, dict) else set()
        for ctx in contexts:
            if expected_keys:
                actual_keys = set(_SCHEMA_KEY_RE.findall(ctx.content))
                preserved = len(expected_keys & actual_keys) / max(len(expected_keys), 1)
                ctx.content = f"[schema_preserved:{preserved:.4f}]\n{ctx.content}"
        return contexts
