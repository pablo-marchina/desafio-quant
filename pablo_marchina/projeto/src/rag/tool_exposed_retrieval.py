"""Tool-exposed retrieval — expose retrieval as a tool."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ToolExposedRetrievalConfig(BaseModel):
    tool_use_boost: float = 0.1


class ToolExposedRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ToolExposedRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        for ctx in contexts:
            tool_signals = len(
                re.findall(r"(?:search|lookup|query|find|retrieve|get|fetch|call|api)", ctx.content.lower())
            )

            query_overlap = sum(1 for w in query.lower().split() if w in ctx.content.lower()) if query else 0

            boost = min(0.3, (tool_signals * 0.02 + query_overlap * 0.01)) + self.cfg.tool_use_boost * 0

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + boost), 4)

        return contexts
