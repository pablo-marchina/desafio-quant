"""requirements inspection RAG

Hypothesis: Evaluate whether requirements inspection RAG improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RequirementsInspectionRag:
    """requirements inspection RAG"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        req_terms = {
            "requirement",
            "shall",
            "must",
            "should",
            "will",
            "acceptable",
            "condition",
            "criterion",
            "specification",
        }

        for ctx in contexts:
            words = set(w.lower().strip(".,!?;:()") for w in ctx.content.split())

            overlap = len(words & req_terms)

            if overlap:
                ctx.relevance_score = min(1.0, ctx.relevance_score + overlap * 0.03)

        return contexts
