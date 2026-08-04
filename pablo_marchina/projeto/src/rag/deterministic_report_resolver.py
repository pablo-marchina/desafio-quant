"""deterministic report resolver

Hypothesis: Evaluate whether deterministic report resolver improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DeterministicReportResolver:
    """deterministic report resolver"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        contexts.sort(key=lambda c: (c.source_id, c.chunk_id))
        for i, ctx in enumerate(contexts):
            ctx.relevance_score = min(1.0, ctx.relevance_score + (i < 5) * 0.02)

        return contexts
