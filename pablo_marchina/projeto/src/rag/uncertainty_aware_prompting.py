"""_uncertainty-aware prompting_

Hypothesis: Evaluate whether uncertainty-aware prompting improves final product output.
Category: 8.8 Reasoning, agents and generation
Expected runtime use: TBD_BY_RUNTIME_REVIEW
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class UncertaintyAwarePrompting:
    """_uncertainty-aware prompting_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
