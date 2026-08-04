from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptApprovalWorkflow:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._approval_state: dict[str, str] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        prompt_name = kwargs.get("prompt_name", "default")
        state = self._approval_state.get(prompt_name, "draft")
        if state == "draft":
            coverage = len(contexts) / max(kwargs.get("expected_contexts", 1), 1)

        if coverage >= 0.8:
            self._approval_state[prompt_name] = "pending_review"

        elif state == "pending_review":
            self._approval_state[prompt_name] = "approved"

        if self._approval_state.get(prompt_name) == "approved":
            for ctx in contexts:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
