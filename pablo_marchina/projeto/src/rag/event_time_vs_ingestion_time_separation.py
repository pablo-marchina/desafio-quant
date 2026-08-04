"""event time vs ingestion time separation

Hypothesis: Evaluate whether event time vs ingestion time separation improves final product output without paid dependency.
Category: 8.39 Temporal RAG and Currentness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class EventTimeVsIngestionTimeSeparation:
    """event time vs ingestion time separation"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import re as _re
        from datetime import datetime

        datetime.now(UTC)

        for ctx in contexts:
            event_years = _re.findall(r"(20\d{2})", ctx.content)

            event_time = max(event_years) if event_years else ""

            ingest_time = ctx.collected_at or ""

            if event_time and ingest_time:
                try:
                    ingest_dt = datetime.fromisoformat(ingest_time.replace("Z", "+00:00"))

                    event_year = int(event_time)

                    if event_year < ingest_dt.year - 1:
                        ctx.relevance_score = max(0.0, ctx.relevance_score - 0.08)

                except (ValueError, TypeError):
                    pass

        return contexts
