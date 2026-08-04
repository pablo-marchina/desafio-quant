from __future__ import annotations

import time
from typing import Any

from src.rag.schemas import RetrievedContext


class LiveCorpusBenchmark:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._freshness_weight = float(config.get("freshness_weight", 0.3)) if isinstance(config, dict) else 0.3

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        now = time.time()
        for ctx in contexts:
            freshness = 0.5

            if ctx.valid_until:
                try:
                    import datetime

                    expiry = datetime.datetime.fromisoformat(ctx.valid_until).timestamp()

                    remaining = expiry - now

                    freshness = min(1.0, max(0.0, remaining / 86400.0))

                except (ValueError, TypeError):
                    pass

                ctx.relevance_score = round(
                    (1 - self._freshness_weight) * ctx.relevance_score + self._freshness_weight * freshness, 4
                )

        return contexts
