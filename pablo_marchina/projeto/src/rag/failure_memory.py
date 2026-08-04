"""failure memory

Hypothesis: Evaluate whether failure memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FailureMemory:
    """failure memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_failures", None):
            self._failures: list[str] = []

        failure_signals = ["error", "fail", "bug", "crash", "regression", "broken", "issue #"]

        for ctx in contexts:
            signal_count = sum(1 for s in failure_signals if s in ctx.content.lower())

            if signal_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + signal_count * 0.05)

            for f in self._failures:
                if f.lower() in ctx.content.lower():
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

        return contexts
