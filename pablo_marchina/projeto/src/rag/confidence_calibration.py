from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ConfidenceCalibratorConfig(BaseModel):
    enabled: bool = True
    temperature: float = 1.0
    beta: float = 1.0


class ConfidenceCalibrator:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ConfidenceCalibratorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        raw_scores = [c.relevance_score for c in contexts]
        if self.config.temperature != 1.0:
            calibrated = [self._temperature_scale(s) for s in raw_scores]

        else:
            calibrated = [self._platt_scale(s) for s in raw_scores]

        for ctx, cal in zip(contexts, calibrated, strict=False):
            ctx.relevance_score = round(max(0.0, min(1.0, cal)), 4)

        return contexts

    def _temperature_scale(self, score: float) -> float:
        if score <= 0.0 or score >= 1.0:
            return score
        logit = math.log(score / (1.0 - score))
        scaled = logit / self.config.temperature
        return 1.0 / (1.0 + math.exp(-scaled))

    def _platt_scale(self, score: float) -> float:
        return 1.0 / (1.0 + math.exp(-self.config.beta * (score - 0.5)))
