"""unanswerable query fallback

Hypothesis: Evaluate whether unanswerable query fallback improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class UnanswerableQueryFallback:
    """unanswerable query fallback"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        threshold = self.config.get("fallback_threshold", 0.2)
        high_score = sum(1 for c in contexts if c.relevance_score >= threshold)

        if high_score < 1:
            contexts.append(
                RetrievedContext(
                    chunk_id="fallback_unknown",
                    source_id="fallback",
                    title="Fallback Response",
                    content="No relevant context found for this query.",
                    product="general",
                    relevance_score=0.1,
                )
            )

        return contexts
