"""search action usefulness

Hypothesis: Evaluate whether search action usefulness improves final product output without paid dependency.
Category: 8.49 Formal Agentic Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SearchActionUsefulness:
    """search action usefulness"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_search_results", None):
            self._search_results: list[float] = []

        avg_score = sum(c.relevance_score for c in contexts) / max(len(contexts), 1)

        self._search_results.append(avg_score)

        self._search_results = self._search_results[-50:]

        for ctx in contexts:
            usefulness = avg_score > 0.3

            if usefulness:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
