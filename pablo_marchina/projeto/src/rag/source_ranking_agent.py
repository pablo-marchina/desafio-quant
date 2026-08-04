"""Source ranking agent — rank sources via agent evaluation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SourceRankingAgentConfig(BaseModel):
    top_k_sources: int = 5


class SourceRankingAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SourceRankingAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        source_stats: dict[str, list[float]] = defaultdict(list)
        for ctx in contexts:
            source_stats[ctx.source_id].append(ctx.relevance_score)
        source_avg = {sid: sum(scores) / len(scores) for sid, scores in source_stats.items()}
        ranked = sorted(source_avg.items(), key=lambda x: x[1], reverse=True)
        top_sources = {sid for sid, _ in ranked[: self.cfg.top_k_sources]}
        result = []
        for ctx in contexts:
            if ctx.source_id in top_sources:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score + 0.05), 4)
                result.append(ctx)
            else:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.05), 4)
                result.append(ctx)
        return result
