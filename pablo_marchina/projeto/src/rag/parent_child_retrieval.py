from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ParentChildRetrievalConfig(BaseModel):
    enabled: bool = True
    max_parents: int = 5
    min_children_for_parent: int = 2


class ParentChildRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = ParentChildRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        groups: dict[str, list[RetrievedContext]] = {}
        for ctx in contexts:
            parent_key = ctx.source_id or ctx.title
            groups.setdefault(parent_key, []).append(ctx)
        selected: list[RetrievedContext] = []
        for children in groups.values():
            if len(children) >= self.config.min_children_for_parent:
                best = max(children, key=lambda c: c.relevance_score)
                best.relevance_score = round(min(best.relevance_score + 0.1, 1.0), 4)
                selected.append(best)
            else:
                selected.extend(children)
        selected.sort(key=lambda c: c.relevance_score, reverse=True)
        return selected[: self.config.max_parents]
