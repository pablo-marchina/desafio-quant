"""Opik

Hypothesis: Evaluate whether Opik improves final product output without paid dependency.
Category: 8.40 Evaluation Stack and Benchmarks
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class Opik:
    """Opik — score contexts via simulated LLM-as-judge metadata."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            query = kwargs.get("query", "")
            query_terms = set(query.lower().split()) if query else set()
            for ctx in contexts:
                overlap = len(query_terms & set(ctx.content.lower().split())) if query_terms else 0

                relevance = overlap / max(len(query_terms), 1) if query_terms else 0.5

                has_url = 0.1 if ctx.url else 0.0

                has_gap = 0.1 if ctx.gap_types else 0.0

                ctx.relevance_score = min(1.0, max(0.0, relevance * 0.6 + has_url + has_gap))

        return contexts
