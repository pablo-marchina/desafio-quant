"""Truth maintenance system — maintain truth in graph."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class TruthMaintenanceSystemConfig(BaseModel):
    support_threshold: int = 2


class TruthMaintenanceSystem:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = TruthMaintenanceSystemConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        claim_support: dict[str, list[RetrievedContext]] = defaultdict(list)
        for ctx in contexts:
            key = ctx.content[:100]

            claim_support[key].append(ctx)

            for ctx in contexts:
                key = ctx.content[:100]

                supporters = claim_support.get(key, [])

                support_count = len(supporters)

                if support_count >= self.cfg.support_threshold:
                    ctx.relevance_score = round(min(1.0, ctx.relevance_score * (1.0 + 0.05 * support_count)), 4)

                elif support_count == 1 and len(contexts) > 1:
                    ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.05), 4)

        return contexts
