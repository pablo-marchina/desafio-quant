"""tool limitation disclosure

Hypothesis: Evaluate whether tool limitation disclosure improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolLimitationDisclosure:
    """tool limitation disclosure"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_tool_limitations", None):
            self._tool_limitations: set[str] = set()

        limitation = kwargs.get("limitation", "")

        if limitation:
            self._tool_limitations.add(str(limitation))

        for ctx in contexts:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.03)

        return contexts
