"""retrieval feedback memory

Hypothesis: Evaluate whether retrieval feedback memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrievalFeedbackMemory:
    """retrieval feedback memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_feedback", None):
            self._feedback: dict[str, float] = {}

        for ctx in contexts:
            feed_score = self._feedback.get(ctx.chunk_id, 0.0)

            ctx.relevance_score = min(1.0, max(0.0, ctx.relevance_score + feed_score))

        if "chunk_id" in kwargs and "feedback_score" in kwargs:
            self._feedback[str(kwargs["chunk_id"])] = float(kwargs["feedback_score"])

        return contexts
