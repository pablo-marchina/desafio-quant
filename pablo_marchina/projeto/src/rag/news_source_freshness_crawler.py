from __future__ import annotations

from datetime import UTC
from typing import Any

from src.rag.schemas import RetrievedContext


class NewsSourceFreshnessCrawler:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._freshness_scores: dict[str, float] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        from datetime import datetime

        now = datetime.now(UTC)
        for ctx in contexts:
            ts_str = ctx.collected_at or ctx.valid_from or ""

            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                    hours_old = (now - dt).total_seconds() / 3600

                    freshness_bonus = max(0.0, (72 - hours_old) / 72.0) * 0.25

                    ctx.relevance_score = min(1.0, ctx.relevance_score + freshness_bonus)

                    self._freshness_scores[ctx.chunk_id] = hours_old

                except (ValueError, TypeError):
                    pass

        return contexts
