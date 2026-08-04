from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class BayesianScorerConfig(BaseModel):
    enabled: bool = True
    alpha_prior: float = 1.0
    beta_prior: float = 1.0


class BayesianScorer:
    def __init__(self, config: Any | None = None) -> None:
        self.config = BayesianScorerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            posterior = self._bayesian_score(ctx)

            ctx.relevance_score = round(posterior, 4)

        return contexts

    def _bayesian_score(self, ctx: RetrievedContext) -> float:
        content = ctx.content.lower()
        pos_words = ["supports", "compatible", "available", "validated", "confirmed"]
        neg_words = ["unsupported", "incompatible", "unavailable", "deprecated", "limited"]
        positive_signals = sum(1 for w in pos_words if w in content)
        negative_signals = sum(1 for w in neg_words if w in content)
        alpha = self.config.alpha_prior + positive_signals
        beta = self.config.beta_prior + negative_signals
        posterior_mean = alpha / (alpha + beta)
        return max(0.0, min(1.0, posterior_mean))
