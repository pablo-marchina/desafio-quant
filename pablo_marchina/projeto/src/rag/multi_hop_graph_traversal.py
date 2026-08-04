"""Multi-hop graph traversal — traverse graph multi-hop."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class MultiHopGraphTraversalConfig(BaseModel):
    max_hops: int = 3


class MultiHopGraphTraversal:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = MultiHopGraphTraversalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entity_map: dict[str, list[int]] = defaultdict(list)
        for i, ctx in enumerate(contexts):
            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

            for e in entities:
                entity_map[e].append(i)

                for ctx in contexts:
                    idx = contexts.index(ctx)

                    reachable = {idx}

                    frontier = {idx}

                    for _ in range(self.cfg.max_hops):
                        new_frontier = set()

                        for fi in frontier:
                            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", contexts[fi].content))

                            for e in entities:
                                for ni in entity_map.get(e, []):
                                    if ni not in reachable:
                                        reachable.add(ni)

                                        new_frontier.add(ni)

                                        frontier = new_frontier

                                        if not frontier:
                                            break

                                        hop_score = min(0.3, (len(reachable) - 1) * 0.02)

                                        ctx.relevance_score = round(min(1.0, ctx.relevance_score + hop_score), 4)

        return contexts
