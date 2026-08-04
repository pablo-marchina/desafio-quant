"""visual citation

Hypothesis: Evaluate whether visual citation improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class VisualCitation:
    """visual citation"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        visual_markers = ["figure", "table", "chart", "graph", "image", "diagram", "screenshot", "visual", "plot"]

        for ctx in contexts:
            vc = sum(1 for m in visual_markers if m.lower() in ctx.content.lower())

            if vc:
                ctx.relevance_score = min(1.0, ctx.relevance_score + vc * 0.04)

        return contexts
