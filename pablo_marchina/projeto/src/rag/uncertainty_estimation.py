from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext

_UNCERTAINTY_WORDS = [
    "may",
    "might",
    "could",
    "possibly",
    "perhaps",
    "likely",
    "unlikely",
    "probably",
    "maybe",
    "uncertain",
    "unknown",
    "unclear",
    "not specified",
    "not documented",
    "not defined",
    "approximately",
    "roughly",
    "about",
    "around",
    "nearly",
    "depends",
    "varies",
    "depending",
    "case by case",
    "suggest",
    "indicate",
    "appear",
    "seem",
    "estimated",
    "projected",
    "forecast",
    "predicted",
]


class UncertaintyEstimatorConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = True


class UncertaintyEstimator:
    def __init__(self, config: Any | None = None) -> None:
        self.config = UncertaintyEstimatorConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            uncertainty = self._estimate(ctx)

            ctx.relevance_score = round(ctx.relevance_score * (1.0 - uncertainty), 4)

        return contexts

    def _estimate(self, ctx: RetrievedContext) -> float:
        content = ctx.content.lower()
        words = content.split()
        if not words:
            return 0.5
        matches = sum(1 for w in _UNCERTAINTY_WORDS if w in content)
        uncertainty = matches / max(len(words) * 0.05, 1.0)
        return min(uncertainty, 0.95)
