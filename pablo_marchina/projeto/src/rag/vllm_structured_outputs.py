from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class VllmStructuredOutputs:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re

        for ctx in contexts:
            has_json = bool(re.search(r"\{[^}]+\}", ctx.content))

            has_list = bool(re.search(r"\[[^\]]+\]", ctx.content))

            has_schema = bool(re.search(r"(?:type|properties|items|required)\s*:", ctx.content))

            structure_score = sum([has_json, has_list, has_schema]) * 0.1

            ctx.relevance_score = min(1.0, ctx.relevance_score + structure_score)

        return contexts
