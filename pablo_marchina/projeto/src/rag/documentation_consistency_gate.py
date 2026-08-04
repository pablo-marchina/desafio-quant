"""documentation consistency gate

Hypothesis: Evaluate whether documentation consistency gate improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DocumentationConsistencyGate:
    """documentation consistency gate"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            has_overview = "overview" in ctx.title.lower() or "overview" in ctx.content.lower()

            has_detail = len(ctx.content) > 200

            if has_overview and has_detail:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

            elif not has_detail:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
