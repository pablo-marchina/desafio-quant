"""Hierarchical retrieval interface — hierarchical retrieval API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class HierarchicalRetrievalInterfaceConfig(BaseModel):
    top_k_groups: int = 3


class HierarchicalRetrievalInterface:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = HierarchicalRetrievalInterfaceConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts
        groups: dict[str, list[RetrievedContext]] = {}
        for ctx in contexts:
            key = ctx.gap_types[0] if ctx.gap_types else ctx.product
            groups.setdefault(key, []).append(ctx)
        result = []
        for _key, members in groups.items():
            members.sort(key=lambda c: c.relevance_score, reverse=True)
            top = members[: self.cfg.top_k_groups]
            for ctx in top:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.1), 4)
                result.append(ctx)
        return result
