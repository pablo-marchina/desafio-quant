"""reason-then-structure generation

Hypothesis: Evaluate whether reason-then-structure generation improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReasonThenStructureGeneration:
    """reason-then-structure generation"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            has_structure = any(m in ctx.content for m in ["1.", "2.", "first", "second", "step", "phase", "stage"])

            if has_structure:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
