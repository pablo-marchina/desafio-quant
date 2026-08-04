"""mandatory citation mode

Hypothesis: Evaluate whether mandatory citation mode improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MandatoryCitationMode:
    """mandatory citation mode"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if not ctx.url:
                ctx.relevance_score = max(0.0, min(ctx.relevance_score, 0.3))

            else:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

        return contexts
