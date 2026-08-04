"""requirement-to-test traceability

Hypothesis: Evaluate whether requirement-to-test traceability improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RequirementToTestTraceability:
    """requirement-to-test traceability"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_req_trace", None):
            self._req_trace: dict[str, list[str]] = {}

        for ctx in contexts:
            is_req = any(w in ctx.content.lower() for w in ["shall", "must", "requirement"])

            is_test = any(w in ctx.content.lower() for w in ["test", "assert", "verify"])

            key = "req" if is_req else "test" if is_test else "other"

            if key not in self._req_trace:
                self._req_trace[key] = []

            self._req_trace[key].append(ctx.chunk_id)

            if is_req and "test" in self._req_trace:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

            if is_test and "req" in self._req_trace:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
