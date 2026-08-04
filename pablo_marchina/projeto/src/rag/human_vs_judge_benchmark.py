from __future__ import annotations

import random
from typing import Any

from src.rag.schemas import RetrievedContext


class HumanVsJudgeBenchmark:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._rng = random.Random(42)

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                noise = self._rng.uniform(-0.1, 0.1)

                ctx.relevance_score = round(max(0.0, min(1.0, ctx.relevance_score + noise)), 4)

        return contexts
