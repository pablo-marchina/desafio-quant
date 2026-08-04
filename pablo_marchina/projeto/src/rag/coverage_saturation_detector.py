"""coverage saturation detector

Hypothesis: Evaluate whether coverage saturation detector improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CoverageSaturationDetector:
    """coverage saturation detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_saturation", None):
            self._saturation: dict[str, int] = {}

        for ctx in contexts:
            key = ctx.source_id

            self._saturation[key] = self._saturation.get(key, 0) + 1

            if self._saturation[key] > 3:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.15)

        return contexts
