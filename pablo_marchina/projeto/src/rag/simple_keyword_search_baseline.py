"""simple keyword search baseline

Hypothesis: Evaluate whether simple keyword search baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SimpleKeywordSearchBaseline:
    """simple keyword search baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        terms = set(query.lower().split()) if query else set()

        for ctx in contexts:
            if not terms:
                ctx.relevance_score = 0.0

                continue

            words = set(ctx.content.lower().split())

            overlap = len(terms & words)

            ctx.relevance_score = overlap / len(terms) if terms else 0.0

        return contexts
