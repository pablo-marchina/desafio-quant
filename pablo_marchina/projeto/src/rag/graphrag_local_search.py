"""GraphRAG local search — local graph search within neighborhoods."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphragLocalSearchConfig(BaseModel):
    neighborhood_size: int = 3


class GraphragLocalSearch:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphragLocalSearchConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        entity_map: dict[str, list[int]] = {}
        for i, ctx in enumerate(contexts):
            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

            for e in entities:
                entity_map.setdefault(e, []).append(i)

                for ctx in contexts:
                    idx = contexts.index(ctx)

                    local_relevance = 0.0

                    seen = {idx}

                    for e in set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content)):
                        for ni in entity_map.get(e, []):
                            if ni not in seen:
                                local_relevance += contexts[ni].relevance_score * 0.1

                                seen.add(ni)

                                ctx.relevance_score = round(min(1.0, ctx.relevance_score + local_relevance), 4)

        return contexts
