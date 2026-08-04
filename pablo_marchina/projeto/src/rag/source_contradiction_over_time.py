"""source contradiction over time

Hypothesis: Evaluate whether source contradiction over time improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceContradictionOverTime:
    """source contradiction over time"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_source_history", None):
            self._source_history: dict[str, list[tuple[str, float]]] = {}

        for ctx in contexts:
            if ctx.source_id not in self._source_history:
                self._source_history[ctx.source_id] = []

            self._source_history[ctx.source_id].append((ctx.content[:100], ctx.relevance_score))

            entries = self._source_history[ctx.source_id]

            if len(entries) >= 2:
                prev_content = entries[-2][0]

                curr_content = entries[-1][0]

                if prev_content and curr_content and prev_content != curr_content:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
