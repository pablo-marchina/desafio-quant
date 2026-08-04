"""tool choice audit

Hypothesis: Evaluate whether tool choice audit improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolChoiceAudit:
    """tool choice audit"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_tool_choices", None):
            self._tool_choices: list[str] = []

        for ctx in contexts:
            tool_keywords = ["used", "called", "invoked", "executed"]

            if any(k in ctx.content.lower() for k in tool_keywords):
                self._tool_choices.append(ctx.chunk_id)

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.01)

        return contexts
