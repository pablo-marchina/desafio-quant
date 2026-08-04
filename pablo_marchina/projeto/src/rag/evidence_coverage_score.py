"""evidence coverage score

Hypothesis: Evaluate whether evidence coverage score improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class EvidenceCoverageScore:
    """evidence coverage score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_evidence_map", None):
            self._evidence_map: dict[str, set[str]] = {}

        for ctx in contexts:
            gap_key = ", ".join(ctx.gap_types) if ctx.gap_types else "general"

            if gap_key not in self._evidence_map:
                self._evidence_map[gap_key] = set()

            self._evidence_map[gap_key].add(ctx.chunk_id)

        for ctx in contexts:
            gap_key = ", ".join(ctx.gap_types) if ctx.gap_types else "general"

            ev_count = len(self._evidence_map.get(gap_key, set()))

            ctx.relevance_score = min(1.0, ctx.relevance_score + min(ev_count * 0.01, 0.2))

        return contexts
