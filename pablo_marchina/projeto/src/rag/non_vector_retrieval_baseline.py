"""non-vector retrieval baseline

Hypothesis: Evaluate whether non-vector retrieval baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class NonVectorRetrievalBaseline:
    """non-vector retrieval baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        query_terms = set(query.lower().split()) if query else set()

        for ctx in contexts:
            title_bonus = 0.2 if any(t in ctx.title.lower() for t in query_terms) else 0.0

            content_matches = sum(1 for t in query_terms if t in ctx.content.lower())

            score = (content_matches / max(len(query_terms), 1)) * 0.8 + title_bonus

            ctx.relevance_score = min(1.0, score)

        return contexts
