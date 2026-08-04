from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HumanReviewedDisclosure:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            high_impact = ctx.relevance_score > 0.8

            low_confidence = ctx.relevance_score < 0.3

            if high_impact or low_confidence:
                ctx.content = ctx.content + f" [HUMAN_REVIEW_REQUIRED: impact={ctx.relevance_score:.2f}]"

        return contexts
