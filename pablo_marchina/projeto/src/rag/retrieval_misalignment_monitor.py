"""_retrieval misalignment monitor_

Hypothesis: Evaluate whether retrieval misalignment monitor improves final product output without paid dependency.
Category: 8.49 Formal Agentic RAG Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrievalMisalignmentMonitor:
    """_retrieval misalignment monitor_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._misalignment_log: list[dict] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        query_terms = set(query.lower().split()) if query else set()
        for ctx in contexts:
            content_terms = set(ctx.content.lower().split())

        if query_terms:
            overlap = len(query_terms & content_terms)

            alignment = overlap / max(len(query_terms), 1)

            misalignment = 1.0 - alignment

        else:
            misalignment = 0.5

            self._misalignment_log.append(
                {
                    "chunk_id": ctx.chunk_id,
                    "misalignment": round(misalignment, 3),
                }
            )

            self._misalignment_log = self._misalignment_log[-200:]

        if misalignment > 0.7:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

        elif misalignment > 0.4:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.03)

        return contexts
