"""_read-after-search policy_

Hypothesis: Evaluate whether read-after-search policy improves final product output without paid dependency.
Category: 8.49 Formal Agentic RAG Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReadAfterSearchPolicy:
    """_read-after-search policy_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._policy_state: dict[str, str] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        action = kwargs.get("action", "read")
        for ctx in contexts:
            key = ctx.source_id

        if action == "search":
            self._policy_state[key] = "searched"

        elif action == "read":
            prev_state = self._policy_state.get(key, "none")

        if prev_state == "none":
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

        elif prev_state == "searched":
            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

            self._policy_state[key] = "read"

        elif action == "generate":
            if self._policy_state.get(key) == "read":
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.03)

        else:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
