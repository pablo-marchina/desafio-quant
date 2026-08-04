"""test-aware retrieval

Hypothesis: Evaluate whether test-aware retrieval improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class TestAwareRetrieval:
    """test-aware retrieval"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        test_markers = ["test_", "_test", "def test", "class test", "it should", "describe", "assert", "expect"]

        for ctx in contexts:
            marker_count = sum(1 for m in test_markers if m.lower() in ctx.content.lower())

            if marker_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + marker_count * 0.03)

        return contexts
