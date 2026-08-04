"""_failure-case registry_

Hypothesis: Evaluate whether failure-case registry improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FailureCaseRegistry:
    """_failure-case registry_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._registry: list[dict] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        failure_cases = [
            {
                "chunk_id": c.chunk_id,
                "source_id": c.source_id,
                "score": c.relevance_score,
                "gap_types": list(c.gap_types),
                "failure_reason": kwargs.get("failure_reason", "low_quality"),
            }
            for c in contexts
            if c.relevance_score < 0.3
        ]
        self._registry.extend(failure_cases)
        self._registry = self._registry[-500:]
        failure_count = len(failure_cases)
        for ctx in contexts:
            if failure_count > len(contexts) * 0.5:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
