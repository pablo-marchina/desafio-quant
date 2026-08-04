"""_LM Format Enforcer_

Hypothesis: Evaluate whether LM Format Enforcer improves final product output without paid dependency.
Category: 8.32 Structured Output and Constrained Decoding
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class LmFormatEnforcer:
    """_LM Format Enforcer_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
