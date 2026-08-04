"""Entity resolution — resolve entity references."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class EntityResolutionConfig(BaseModel):
    resolution_bonus: float = 0.1


class EntityResolution:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = EntityResolutionConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entity_occurrences: dict[str, set[str]] = defaultdict(set)
        for ctx in contexts:
            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

            for e in entities:
                entity_occurrences[e].add(ctx.chunk_id)

                for ctx in contexts:
                    entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

                    resolved = 0

                    for e in entities:
                        if len(entity_occurrences.get(e, set())) > 1:
                            resolved += 1

                            resolution_rate = resolved / max(1, len(entities))

                            ctx.relevance_score = round(
                                min(1.0, ctx.relevance_score + resolution_rate * self.cfg.resolution_bonus), 4
                            )

        return contexts
