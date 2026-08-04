"""number manipulation trap

Hypothesis: Evaluate whether number manipulation trap improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class NumberManipulationTrap:
    """number manipulation trap"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re as _re

        for ctx in contexts:
            numbers = _re.findall(r"\b\d+(?:\.\d+)?\b", ctx.content)

            num_count = len(numbers)

            if num_count > 10:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
