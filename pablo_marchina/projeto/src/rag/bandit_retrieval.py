from __future__ import annotations

import math
import random
from typing import Any

from src.rag.schemas import RetrievedContext


class BanditRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._bandit_stats: dict[str, list[float]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        epsilon = self.config.get("epsilon", 0.15)
        for ctx in contexts:
            if ctx.chunk_id not in self._bandit_stats:
                self._bandit_stats[ctx.chunk_id] = []

                self._bandit_stats[ctx.chunk_id].append(ctx.relevance_score)

                avg = sum(self._bandit_stats[ctx.chunk_id]) / len(self._bandit_stats[ctx.chunk_id])

            if random.random() < epsilon:
                ctx.relevance_score = round(random.uniform(0.0, 0.5), 4)

            else:
                bonus = math.log(len(self._bandit_stats[ctx.chunk_id]) + 1) * 0.02

                ctx.relevance_score = round(min(1.0, avg + bonus), 4)

        return contexts
