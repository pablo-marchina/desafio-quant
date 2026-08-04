"""architecture review RAG

Hypothesis: Evaluate whether architecture review RAG improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ArchitectureReviewRag:
    """architecture review RAG"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        arch_terms = {
            "architecture",
            "design",
            "pattern",
            "component",
            "module",
            "layer",
            "dependency",
            "interface",
            "abstraction",
        }

        for ctx in contexts:
            words = set(w.lower().strip(".,!?;:()") for w in ctx.content.split())

            overlap = len(words & arch_terms)

            if overlap:
                ctx.relevance_score = min(1.0, ctx.relevance_score + overlap * 0.03)

        return contexts
