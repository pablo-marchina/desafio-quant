"""schema repair success rate

Hypothesis: Evaluate whether schema repair success rate improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SchemaRepairSuccessRate:
    """schema repair success rate"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_repair_stats", None):
            self._repair_stats: dict[str, list[bool]] = {}

        for ctx in contexts:
            required = ["chunk_id", "source_id", "content"]

            valid = all(getattr(ctx, f, None) for f in required)

            repair_key = ctx.source_id.split("_")[0] if "_" in ctx.source_id else ctx.source_id

            if repair_key not in self._repair_stats:
                self._repair_stats[repair_key] = []

            self._repair_stats[repair_key].append(valid)

            success_rate = sum(self._repair_stats[repair_key]) / max(len(self._repair_stats[repair_key]), 1)

            if not valid and success_rate > 0.5:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.1)

        return contexts
