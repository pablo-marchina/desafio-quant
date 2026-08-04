from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class UnitEconomicsDashboard:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._dashboard: dict[str, list[float]] = {"scores": [], "costs": []}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scores = [c.relevance_score for c in contexts]
        costs = [len(c.content.split()) * 0.001 for c in contexts]
        self._dashboard["scores"].extend(scores)
        self._dashboard["costs"].extend(costs)
        self._dashboard["scores"] = self._dashboard["scores"][-500:]
        self._dashboard["costs"] = self._dashboard["costs"][-500:]
        avg_cost = sum(costs) / max(len(costs), 1)
        for ctx in contexts:
            ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score - avg_cost * 0.1))

        return contexts
