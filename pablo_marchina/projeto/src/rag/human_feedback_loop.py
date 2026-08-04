from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HumanFeedbackLoop:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        feedback = kwargs.get("feedback", "")
        if feedback:
            for ctx in contexts:
                adjustment = 0.15 if "relevant" in feedback.lower() else -0.1

                ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score + adjustment))

        return contexts
