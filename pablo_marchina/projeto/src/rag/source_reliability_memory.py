"""source reliability memory

Hypothesis: Evaluate whether source reliability memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceReliabilityMemory:
    """source reliability memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_reliability", None):
            self._reliability: dict[str, float] = {}

        for ctx in contexts:
            base = self._reliability.get(ctx.source_id, 0.5)

            bonus = self._reliability.get(ctx.source_id, 0.0)

            ctx.relevance_score = min(1.0, ctx.relevance_score * (0.5 + base) + bonus)

        if "source_id" in kwargs and "reliability_delta" in kwargs:
            sid = str(kwargs["source_id"])

            self._reliability[sid] = self._reliability.get(sid, 0.5) + float(kwargs["reliability_delta"])

        return contexts
