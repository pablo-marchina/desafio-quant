"""tool call necessity

Hypothesis: Evaluate whether tool call necessity improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolCallNecessity:
    """tool call necessity"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_tool_call_log", None):
            self._tool_call_log: list[dict] = []

        for ctx in contexts:
            essential = any(k in ctx.content.lower() for k in ["required", "necessary", "need to"])

            if essential:
                self._tool_call_log.append({"chunk": ctx.chunk_id, "essential": True})

                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
