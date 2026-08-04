from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ConformalRiskControl:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._risk_level = float(config.get("risk_level", 0.1)) if isinstance(config, dict) else 0.1

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            scores = [ctx.relevance_score for ctx in contexts]
            scores.sort()
            threshold_idx = int((1.0 - self._risk_level) * len(scores))
            threshold = scores[threshold_idx] if threshold_idx < len(scores) else 0.0
            for ctx in contexts:
                if ctx.relevance_score < threshold:
                    ctx.relevance_score = round(ctx.relevance_score * (1.0 - self._risk_level), 4)

        return contexts
