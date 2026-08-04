"""_rubric-based generation_

Hypothesis: Evaluate whether rubric-based generation improves final product output.
Category: 8.8 Reasoning, agents and generation
Expected runtime use: TBD_BY_RUNTIME_REVIEW
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RubricBasedGeneration:
    """_rubric-based generation_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
