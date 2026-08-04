"""validity interval per evidence

Hypothesis: Evaluate whether validity interval per evidence improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class ValidityIntervalPerEvidence:
    """validity interval per evidence"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        from datetime import datetime

        now = datetime.now(UTC)

        for ctx in contexts:
            vf = ctx.valid_from

            vu = ctx.valid_until

            try:
                vf_dt = datetime.fromisoformat(vf.replace("Z", "+00:00")) if vf else None

                vu_dt = datetime.fromisoformat(vu.replace("Z", "+00:00")) if vu else None

                if vf_dt and now < vf_dt:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.2)

                if vu_dt and now > vu_dt:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.3)

                if vf_dt and now >= vf_dt and (not vu_dt or now <= vu_dt):
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.1)

            except (ValueError, TypeError):
                pass

        return contexts
