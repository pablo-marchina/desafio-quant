"""missing source detector

Hypothesis: Evaluate whether missing source detector improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MissingSourceDetector:
    """missing source detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if not ctx.source_id:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

            if not ctx.url:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

        return contexts
