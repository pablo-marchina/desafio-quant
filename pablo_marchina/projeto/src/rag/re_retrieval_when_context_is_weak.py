"""_re-retrieval when context is weak_

Hypothesis: Evaluate whether re-retrieval when context is weak improves final product output without paid dependency.
Category: 8.34 Verifier-Guided and Corrective RAG
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReRetrievalWhenContextIsWeak:
    """_re-retrieval when context is weak_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._re_retrieval_requests: list[str] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        weak_threshold = self.config.get("weak_threshold", 0.25)
        short_content_threshold = self.config.get("min_content_length", 50)
        for ctx in contexts:
            is_weak = ctx.relevance_score < weak_threshold

            is_too_short = len(ctx.content) < short_content_threshold

            needs_re_retrieval = is_weak or is_too_short

        if needs_re_retrieval:
            self._re_retrieval_requests.append(ctx.chunk_id)

            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.08)

        else:
            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

            self._re_retrieval_requests = self._re_retrieval_requests[-200:]
        return contexts
