"""machine-generated disclosure

Hypothesis: Evaluate whether machine-generated disclosure improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MachineGeneratedDisclosure:
    """machine-generated disclosure"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_machine_generated_flag", None):
            self._machine_generated_flag: bool = True

        for ctx in contexts:
            ctx.relevance_score = max(0.0, ctx.relevance_score - 0.02)

        return contexts
