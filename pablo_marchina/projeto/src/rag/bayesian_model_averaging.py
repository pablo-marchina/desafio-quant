from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class BayesianModelAveraging:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._prior = float(config.get("prior", 0.5)) if isinstance(config, dict) else 0.5
        self._prior_weight = float(config.get("prior_weight", 0.3)) if isinstance(config, dict) else 0.3

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                posterior = self._prior_weight * self._prior + (1 - self._prior_weight) * ctx.relevance_score

                ctx.relevance_score = round(posterior, 4)

        return contexts
