"""tool use capability score

Hypothesis: Evaluate whether tool use capability score improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolUseCapabilityScore:
    """tool use capability score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        capability_hints = {"search": 0.3, "retrieve": 0.3, "generate": 0.2, "embed": 0.1, "rerank": 0.1}

        for ctx in contexts:
            score = 0.0

            for tool, cap in capability_hints.items():
                if tool in ctx.content.lower():
                    score += cap

            ctx.relevance_score = min(1.0, ctx.relevance_score + score)

        return contexts
