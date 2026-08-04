"""Graph consistency checker — consistency checker component."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphConsistencyCheckerConfig(BaseModel):
    conflict_penalty: float = 0.1


class GraphConsistencyChecker:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphConsistencyCheckerConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entity_sentiment: dict[str, list[float]] = defaultdict(list)
        for ctx in contexts:
            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

            for e in entities:
                entity_sentiment[e].append(ctx.relevance_score)

                conflict_count: dict[str, int] = defaultdict(int)
                for e, scores in entity_sentiment.items():
                    if len(scores) > 1:
                        variance = sum((s - sum(scores) / len(scores)) ** 2 for s in scores) / len(scores)

                        if variance > 0.1:
                            conflict_count[e] = len(scores)

                            for ctx in contexts:
                                entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

                                conflicts = sum(conflict_count.get(e, 0) for e in entities)

                                penalty = min(self.cfg.conflict_penalty, conflicts * 0.02)

                                ctx.relevance_score = round(max(0.0, ctx.relevance_score - penalty), 4)

        return contexts
