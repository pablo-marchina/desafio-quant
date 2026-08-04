"""tool selection policy

Hypothesis: Evaluate whether tool selection policy improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolSelectionPolicy:
    """tool selection policy"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        policy_tags = {
            "search": "retrieval",
            "read": "retrieval",
            "generate": "generation",
            "embed": "encoding",
            "rerank": "ranking",
        }

        for ctx in contexts:
            for tool, _category in policy_tags.items():
                if tool in ctx.content.lower():
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
