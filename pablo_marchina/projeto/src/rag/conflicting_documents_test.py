"""conflicting documents test

Hypothesis: Evaluate whether conflicting documents test improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ConflictingDocumentsTest:
    """conflicting documents test"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_seen_claims", None):
            self._seen_claims: dict[str, set[str]] = {}

        for ctx in contexts:
            statements = set(s.strip() for s in ctx.content.split(".") if len(s) > 30)

            for other_id, other_stmts in self._seen_claims.items():
                if other_id == ctx.chunk_id:
                    continue

                overlap = statements & other_stmts

                if overlap:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.08)

            self._seen_claims[ctx.chunk_id] = statements

        return contexts
