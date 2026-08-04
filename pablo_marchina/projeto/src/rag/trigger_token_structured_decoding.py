from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TRIGGER_PATTERN = re.compile(r"\b(?:BEGIN|START|OUTPUT|RESULT|ANSWER|JSON|XML|YAML|STRUCTURED)\b")


class TriggerTokenStructuredDecoding:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        trigger_tokens = kwargs.get("trigger_tokens", None)
        tokens = trigger_tokens if trigger_tokens else _TRIGGER_PATTERN
        for ctx in contexts:
            matches = (
                tokens.findall(ctx.content)
                if isinstance(tokens, re.Pattern)
                else [t for t in tokens if t.lower() in ctx.content.lower()]
            )
            ctx.content = f"[triggers:{len(matches)}]\n{ctx.content}"
        return contexts
