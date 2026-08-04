"""component blame assignment

Hypothesis: Evaluate whether component blame assignment improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ComponentBlameAssignment:
    """component blame assignment"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_blame_map", None):
            self._blame_map: dict[str, int] = {}

        for ctx in contexts:
            component = ctx.source_id.split(".")[0] if "." in ctx.source_id else ctx.source_id

            self._blame_map[component] = self._blame_map.get(component, 0) + 1

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.01)

        return contexts
