"""Meilisearch

Hypothesis: Evaluate whether Meilisearch improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Meilisearch:
    """Meilisearch"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        typo_tolerance = self.config.get("typo_tolerance", 0.1)
        for ctx in contexts:
            matched_terms = kwargs.get("matched_terms", 0)

            if matched_terms:
                ctx.relevance_score = min(1.0, matched_terms * 0.25 + typo_tolerance)

            else:
                ctx.relevance_score = ctx.relevance_score * 0.9 + 0.1

        return contexts
