"""design document consistency check

Hypothesis: Evaluate whether design document consistency check improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DesignDocumentConsistencyCheck:
    """design document consistency check"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        design_markers = {"architecture", "design", "component", "interface", "module", "system", "overview", "diagram"}

        for ctx in contexts:
            words = set(w.lower().strip(".,!?;:()") for w in ctx.content.split())

            overlap = len(words & design_markers)

            if overlap:
                ctx.relevance_score = min(1.0, ctx.relevance_score + overlap * 0.02)

        return contexts
