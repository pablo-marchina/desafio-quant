"""source acquisition failure summary

Hypothesis: Evaluate whether source acquisition failure summary improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceAcquisitionFailureSummary:
    """source acquisition failure summary"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_acquisition_failures", None):
            self._acquisition_failures: list[dict] = []

        failure = {"reason": kwargs.get("failure_reason", "unknown"), "context_count": len(contexts)}

        self._acquisition_failures.append(failure)

        self._acquisition_failures = self._acquisition_failures[-100:]

        for ctx in contexts:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
