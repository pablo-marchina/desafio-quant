"""final answer coverage score

Hypothesis: Evaluate whether final answer coverage score improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FinalAnswerCoverageScore:
    """final answer coverage score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_answer_topics", None):
            self._answer_topics: list[str] = []

        query = kwargs.get("query", "")

        if query:
            self._answer_topics = query.lower().split()

        covered_terms = set()

        for ctx in contexts:
            text = ctx.content.lower()

            for term in self._answer_topics:
                if term in text:
                    covered_terms.add(term)

        coverage = len(covered_terms) / max(len(self._answer_topics), 1)

        for ctx in contexts:
            if coverage < 0.4:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

            else:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
