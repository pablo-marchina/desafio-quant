"""tool use correctness

Hypothesis: Evaluate whether tool use correctness improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolUseCorrectness:
    """tool use correctness"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        error_markers = ["wrong tool", "incorrect usage", "invalid argument", "unexpected parameter", "tool error"]

        for ctx in contexts:
            if any(e in ctx.content.lower() for e in error_markers):
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.15)

        return contexts
