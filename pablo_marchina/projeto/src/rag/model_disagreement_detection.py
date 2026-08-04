from __future__ import annotations

import random
from typing import Any

from src.rag.schemas import RetrievedContext


class ModelDisagreementDetection:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._rng = random.Random(42)
        self._num_models = int(config.get("num_models", 3)) if isinstance(config, dict) else 3

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                scores = [self._simulate_model_score(ctx.relevance_score) for _ in range(self._num_models)]

                variance = sum((s - sum(scores) / len(scores)) ** 2 for s in scores) / len(scores)

                if variance > 0.1:
                    ctx.relevance_score = round(ctx.relevance_score * (1.0 - variance), 4)

        return contexts

    def _simulate_model_score(self, base: float) -> float:
        noise = self._rng.gauss(0, 0.1)
        return max(0.0, min(1.0, base + noise))
