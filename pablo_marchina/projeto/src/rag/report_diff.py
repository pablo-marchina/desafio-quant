"""report diff

Hypothesis: Evaluate whether report diff improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReportDiff:
    """report diff"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_prev_report_ids", None):
            self._prev_report_ids: set[str] = set()

        cur_ids = {ctx.chunk_id for ctx in contexts}

        self._prev_report_ids - cur_ids

        added = cur_ids - self._prev_report_ids

        for ctx in contexts:
            if ctx.chunk_id in added:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.08)

        self._prev_report_ids = cur_ids

        return contexts
