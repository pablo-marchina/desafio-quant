"""Outline-first generation — outline first."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class OutlineFirstGenerationConfig(BaseModel):
    max_outline_items: int = 5


class OutlineFirstGeneration:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = OutlineFirstGenerationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        topics: OrderedDict[str, list[RetrievedContext]] = OrderedDict()
        for ctx in contexts:
            topic = ctx.title[:50] if ctx.title else ctx.gap_types[0] if ctx.gap_types else "topic"
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(ctx)
        outline = list(topics.keys())[: self.cfg.max_outline_items]
        result: list[RetrievedContext] = []
        for topic in outline:
            items = topics[topic]
            items.sort(key=lambda c: c.relevance_score, reverse=True)
            best = items[0]
            best.relevance_score = round(min(1.0, best.relevance_score * 1.1), 4)
            result.append(best)
        return result
