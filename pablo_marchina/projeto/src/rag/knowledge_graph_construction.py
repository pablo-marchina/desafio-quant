"""Knowledge graph construction — build KG from contexts."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class KnowledgeGraphConstructionConfig(BaseModel):
    min_entity_freq: int = 1


class KnowledgeGraphConstruction:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = KnowledgeGraphConstructionConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entity_contexts: dict[str, list[int]] = defaultdict(list)
        for i, ctx in enumerate(contexts):
            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

            for e in entities:
                entity_contexts[e].append(i)

                adjacency: dict[int, set[int]] = defaultdict(set)
                for _e, indices in entity_contexts.items():
                    if len(indices) >= self.cfg.min_entity_freq:
                        for i in indices:
                            for j in indices:
                                if i != j:
                                    adjacency[i].add(j)

                                    for ctx in contexts:
                                        idx = contexts.index(ctx)

                                        connections = len(adjacency.get(idx, set()))

                                        kg_score = min(0.3, connections * 0.03)

                                        ctx.relevance_score = round(min(1.0, ctx.relevance_score + kg_score), 4)

        return contexts
