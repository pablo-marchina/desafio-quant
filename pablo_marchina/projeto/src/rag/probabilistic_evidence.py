from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ProbabilisticEvidenceScorerConfig(BaseModel):
    enabled: bool = True
    prior_weight: float = 0.3
    likelihood_weight: float = 0.7


class ProbabilisticEvidenceScorer:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ProbabilisticEvidenceScorerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            posterior = self._compute_posterior(ctx)

            ctx.relevance_score = round(posterior, 4)

        return contexts

    def _compute_posterior(self, ctx: RetrievedContext) -> float:
        prior = ctx.relevance_score
        content = ctx.content.lower()
        words = content.split()
        total = len(words)
        evidence_ratio = 0.5
        if total > 0:
            specificity = len(set(words)) / max(total, 1)
            evidence_ratio = min(specificity * 1.5, 1.0)
        likelihood = evidence_ratio
        numerator = prior * likelihood
        denominator = numerator + (1.0 - prior) * (1.0 - likelihood)
        if denominator == 0.0:
            return prior
        posterior = numerator / denominator
        return max(0.0, min(1.0, posterior))
