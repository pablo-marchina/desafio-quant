from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HumanAppealWorkflow:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        appeal_reason = kwargs.get("appeal_reason", "")
        if appeal_reason:
            for ctx in contexts:
                ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score + 0.15))

        return contexts
