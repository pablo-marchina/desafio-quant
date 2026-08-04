"""Community summaries — summarize graph communities."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class CommunitySummariesConfig(BaseModel):
    top_communities: int = 3


class CommunitySummaries:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = CommunitySummariesConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        communities: dict[str, list[RetrievedContext]] = defaultdict(list)
        for ctx in contexts:
            key = ctx.gap_types[0] if ctx.gap_types else ctx.product
            communities[key].append(ctx)
        scored_communities = []
        for key, members in communities.items():
            avg_score = sum(c.relevance_score for c in members) / len(members)
            scored_communities.append((avg_score, key, members))
        scored_communities.sort(key=lambda x: x[0], reverse=True)
        result = []
        for _, _key, members in scored_communities[: self.cfg.top_communities]:
            for ctx in members:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.1), 4)
                result.append(ctx)
        return result
