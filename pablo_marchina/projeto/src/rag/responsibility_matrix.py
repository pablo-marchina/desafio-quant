"""responsibility matrix

Hypothesis: Evaluate whether responsibility matrix improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ResponsibilityMatrix:
    """responsibility matrix"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_responsibility", None):
            self._responsibility: dict[str, list[str]] = {}

        for ctx in contexts:
            owner = ctx.source_id.split("/")[0] if "/" in ctx.source_id else ctx.source_id

            if owner not in self._responsibility:
                self._responsibility[owner] = []

            self._responsibility[owner].append(ctx.chunk_id)

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.01)

        return contexts
