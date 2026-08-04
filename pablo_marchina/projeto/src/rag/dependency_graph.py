"""dependency graph

Hypothesis: Evaluate whether dependency graph improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DependencyGraph:
    """dependency graph"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_dep_graph_data", None):
            self._dep_graph_data: dict[str, list[dict]] = {}

        for ctx in contexts:
            if ctx.source_id not in self._dep_graph_data:
                self._dep_graph_data[ctx.source_id] = []

            for other in contexts:
                if ctx.chunk_id != other.chunk_id and any(
                    w.lower() in other.content.lower() for w in ctx.title.split()
                ):
                    self._dep_graph_data[ctx.source_id].append(
                        {"depends_on": other.chunk_id, "score": other.relevance_score}
                    )

            dep_count = len(self._dep_graph_data.get(ctx.source_id, []))

            if dep_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + dep_count * 0.02)

        return contexts
