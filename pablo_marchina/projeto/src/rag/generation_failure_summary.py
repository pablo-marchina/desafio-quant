"""generation failure summary

Hypothesis: Evaluate whether generation failure summary improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class GenerationFailureSummary:
    """generation failure summary"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_failures", None):
            self._failures: list[dict] = []

        low_score_count = sum(1 for c in contexts if c.relevance_score < 0.3)

        entry = {
            "total_contexts": len(contexts),
            "low_score_count": low_score_count,
            "avg_score": sum(c.relevance_score for c in contexts) / max(len(contexts), 1),
        }

        self._failures.append(entry)

        self._failures = self._failures[-100:]

        return contexts
