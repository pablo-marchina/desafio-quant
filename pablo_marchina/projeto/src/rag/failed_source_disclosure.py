"""failed source disclosure

Hypothesis: Evaluate whether failed source disclosure improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FailedSourceDisclosure:
    """failed source disclosure"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_failed_sources", None):
            self._failed_sources: list[str] = []

        failed_reason = kwargs.get("failed_source", "")

        if failed_reason:
            self._failed_sources.append(failed_reason)

        for ctx in contexts:
            if ctx.source_id in self._failed_sources:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

        return contexts
