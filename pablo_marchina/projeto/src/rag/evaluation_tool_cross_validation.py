from __future__ import annotations

import random
from typing import Any

from src.rag.schemas import RetrievedContext


class EvaluationToolCrossValidation:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._rng = random.Random(42)

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            k = min(5, len(contexts))
            indices = list(range(len(contexts)))
            self._rng.shuffle(indices)
            fold_size = len(indices) // max(k, 1)
            for fold in range(k):
                start = fold * fold_size

                end = start + fold_size if fold < k - 1 else len(indices)

                for idx in range(start, end):
                    if idx < len(contexts):
                        contexts[indices[idx]].relevance_score = round(contexts[indices[idx]].relevance_score * 0.95, 4)

        return contexts
