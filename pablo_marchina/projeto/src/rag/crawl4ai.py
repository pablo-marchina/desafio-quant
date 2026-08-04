"""Crawl4AI

Hypothesis: Evaluate whether Crawl4AI improves final product output without paid dependency.
Category: 8.18 Sourcing and Crawling
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Crawl4ai:
    """Crawl4AI"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_crawl4ai_data", None):
            self._crawl4ai_data: list[dict] = []

        for ctx in contexts:
            self._crawl4ai_data.append({"chunk": ctx.chunk_id, "score": ctx.relevance_score})

        self._crawl4ai_data = self._crawl4ai_data[-500:]

        return contexts
