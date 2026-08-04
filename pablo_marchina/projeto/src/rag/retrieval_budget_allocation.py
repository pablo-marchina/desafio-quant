from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class RetrievalBudgetAllocationConfig(BaseModel):
    enabled: bool = True
    max_contexts: int = 10
    budget_per_gap_type: int = 3


class RetrievalBudgetAllocation:
    def __init__(self, config: Any | None = None) -> None:
        self.config = RetrievalBudgetAllocationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        gap_type: str | None = kwargs.get("gap_type")
        if gap_type:
            gap_contexts = [c for c in contexts if gap_type in c.gap_types]
            other_contexts = [c for c in contexts if gap_type not in c.gap_types]
            gap_contexts.sort(key=lambda c: c.relevance_score, reverse=True)
            other_contexts.sort(key=lambda c: c.relevance_score, reverse=True)
            selected = gap_contexts[: self.config.budget_per_gap_type]
            remaining_budget = self.config.max_contexts - len(selected)
            if remaining_budget > 0:
                selected.extend(other_contexts[:remaining_budget])
            return selected
        sorted_ctx = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        return sorted_ctx[: self.config.max_contexts]
