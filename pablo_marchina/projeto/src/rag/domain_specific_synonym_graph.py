"""domain-specific synonym graph

Hypothesis: Evaluate whether domain-specific synonym graph improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DomainSpecificSynonymGraph:
    """domain-specific synonym graph"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_synonym_graph", None):
            self._synonym_graph: dict[str, list[str]] = {
                "startup": ["company", "venture", "enterprise", "firm"],
                "ai": ["artificial intelligence", "machine intelligence", "cognitive computing"],
                "nvidia": ["nvidia corporation", "nvda", "green team"],
            }

        for ctx in contexts:
            syn_matches = 0.0

            for term, syns in self._synonym_graph.items():
                if term.lower() in ctx.content.lower():
                    syn_matches += 1

                for s in syns:
                    if s.lower() in ctx.content.lower():
                        syn_matches += 0.5

            if syn_matches:
                ctx.relevance_score = min(1.0, ctx.relevance_score + syn_matches * 0.02)

        return contexts
