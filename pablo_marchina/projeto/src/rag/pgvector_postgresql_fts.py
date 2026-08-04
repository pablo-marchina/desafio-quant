"""PGVector PostgreSQL FTS

Hypothesis: Evaluate whether PGVector PostgreSQL FTS improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PgvectorPostgresqlFts:
    """PGVector PostgreSQL FTS"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        fts_weight = self.config.get("fts_weight", 0.4)
        vector_weight = 1.0 - fts_weight

        for ctx in contexts:
            combined = ctx.relevance_score * vector_weight + 0.5 * fts_weight

            ctx.relevance_score = min(1.0, combined)

        return contexts
