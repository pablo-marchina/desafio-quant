"""generic ChatGPT baseline

Hypothesis: Evaluate whether generic ChatGPT baseline improves final product output without paid dependency.
Category: 8.51 Search Backend Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class GenericChatgptBaseline:
    """generic ChatGPT baseline"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        generic_markers = ["i think", "in my opinion", "generally", "as an ai", "based on my training", "typically"]

        for ctx in contexts:
            marker_count = sum(1 for m in generic_markers if m in ctx.content.lower())

            ctx.relevance_score = max(0.0, 0.5 - marker_count * 0.1)

        return contexts
