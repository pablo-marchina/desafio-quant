from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ConformalPredictorConfig(BaseModel):
    enabled: bool = True
    significance_level: float = 0.1
    calib_size: int = 10


class ConformalPredictor:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ConformalPredictorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            scores = [1.0 - c.relevance_score for c in contexts]
            scores.sort()
            n = len(scores)
            q_index = math.ceil((n + 1) * (1.0 - self.config.significance_level)) - 1
            q_index = max(0, min(q_index, n - 1))
            threshold = 1.0 - scores[q_index]
            for ctx in contexts:
                if ctx.relevance_score < threshold:
                    ctx.relevance_score = round(ctx.relevance_score * 0.5, 4)

        return contexts
