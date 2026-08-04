"""mutual exclusivity map

Hypothesis: Evaluate whether mutual exclusivity map improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MutualExclusivityMap:
    """mutual exclusivity map"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_mutual_exclusions", None):
            self._mutual_exclusions: dict[str, list[str]] = {}

        for ctx in contexts:
            for gap in ctx.gap_types:
                if gap not in self._mutual_exclusions:
                    self._mutual_exclusions[gap] = []

                for other_ctx in contexts:
                    if other_ctx.chunk_id != ctx.chunk_id:
                        for other_gap in other_ctx.gap_types:
                            if other_gap != gap and other_ctx.chunk_id not in self._mutual_exclusions[gap]:
                                self._mutual_exclusions[gap].append(other_ctx.chunk_id)

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.01)

        return contexts
