"""tool call ranking

Hypothesis: Evaluate whether tool call ranking improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolCallRanking:
    """tool call ranking"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            num_tools = ctx.content.lower().count("search") + ctx.content.lower().count("retrieve")

            if num_tools:
                ctx.relevance_score = min(1.0, ctx.relevance_score + num_tools * 0.02)

        return contexts
