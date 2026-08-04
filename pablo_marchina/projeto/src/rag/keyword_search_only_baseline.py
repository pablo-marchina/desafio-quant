"""keyword-search-only baseline

Hypothesis: Evaluate whether keyword-search-only baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class KeywordSearchOnlyBaseline:
    """keyword-search-only baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        query_terms = set(query.lower().split()) if query else set()

        for ctx in contexts:
            content_words = set(ctx.content.lower().split())

            overlap = len(query_terms & content_words)

            if query_terms and overlap:
                ctx.relevance_score = overlap / max(len(query_terms), 1)

            else:
                ctx.relevance_score = 0.0

        return contexts
