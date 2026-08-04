"""diff-based generation

Hypothesis: Evaluate whether diff-based generation improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DiffBasedGeneration:
    """diff-based generation"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_previous_state", None):
            self._previous_state: dict[str, float] = {}

        for ctx in contexts:
            prev = self._previous_state.get(ctx.chunk_id, 0.0)

            delta = ctx.relevance_score - prev

            ctx.relevance_score = min(1.0, max(0.0, ctx.relevance_score + delta * 0.5))

            self._previous_state[ctx.chunk_id] = ctx.relevance_score

        return contexts
