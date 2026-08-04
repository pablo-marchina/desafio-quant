from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RecommendationFalsification:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        falsify_terms = {
            "counterexample",
            "exception",
            "alternative",
            "contradicts",
            "disproves",
            "refutes",
            "however",
            "but",
            "although",
        }
        for ctx in contexts:
            content = ctx.content.lower()

            falsify_count = sum(1 for t in falsify_terms if t in content)

        if falsify_count >= 2:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

        elif falsify_count == 1:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.08)

        return contexts
