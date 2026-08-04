"""repository map

Hypothesis: Evaluate whether repository map improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RepositoryMap:
    """repository map"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_repo_map", None):
            self._repo_map: dict[str, list[str]] = {}

        for ctx in contexts:
            path_parts = ctx.source_id.split("/")

            for i in range(1, len(path_parts)):
                prefix = "/".join(path_parts[:i])

                if prefix not in self._repo_map:
                    self._repo_map[prefix] = []

                self._repo_map[prefix].append(ctx.source_id)

            depth = len(path_parts)

            ctx.relevance_score = min(1.0, ctx.relevance_score + min(depth * 0.01, 0.1))

        return contexts
