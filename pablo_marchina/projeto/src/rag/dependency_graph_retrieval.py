"""dependency graph retrieval

Hypothesis: Evaluate whether dependency graph retrieval improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DependencyGraphRetrieval:
    """dependency graph retrieval"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_dep_graph", None):
            self._dep_graph: dict[str, set[str]] = {}

        for ctx in contexts:
            imports = [line for line in ctx.content.split("\n") if line.strip().startswith(("import ", "from "))]

            for imp in imports:
                parts = imp.split()

                if len(parts) >= 2:
                    dep = parts[1].split(".")[0]

                    if dep not in self._dep_graph:
                        self._dep_graph[dep] = set()

                    self._dep_graph[dep].add(ctx.source_id)

            ctx.relevance_score = min(1.0, ctx.relevance_score + len(imports) * 0.02)

        return contexts
