"""synonym merge

Hypothesis: Evaluate whether synonym merge improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SynonymMerge:
    """synonym merge"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_synonym_clusters", None):
            self._synonym_clusters: list[list[str]] = [
                ["startup", "start-up", "new venture", "early-stage company"],
                ["ai", "artificial intelligence", "machine intelligence"],
                ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
            ]

        for ctx in contexts:
            cluster_hits = set()

            for cluster in self._synonym_clusters:
                for term in cluster:
                    if term.lower() in ctx.content.lower():
                        cluster_hits.add(tuple(cluster))

                        break

            if len(cluster_hits) > 1:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
