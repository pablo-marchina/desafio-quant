"""citation graph crawling

Hypothesis: Evaluate whether citation graph crawling improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CitationGraphCrawling:
    """citation graph crawling"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_citation_graph", None):
            self._citation_graph: dict[str, list[str]] = {}

        for ctx in contexts:
            if ctx.source_id not in self._citation_graph:
                self._citation_graph[ctx.source_id] = []

            for other in contexts:
                if (
                    ctx.url
                    and other.url
                    and ctx.url != other.url
                    and any(t.lower() in other.content.lower() for t in ctx.title.split())
                ):
                    self._citation_graph[ctx.source_id].append(other.source_id)

            citation_count = len(self._citation_graph.get(ctx.source_id, []))

            ctx.relevance_score = min(1.0, ctx.relevance_score + citation_count * 0.02)

        return contexts
