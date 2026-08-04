"""Graph consistency checking — check graph consistency."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphConsistencyCheckingConfig(BaseModel):
    consistency_threshold: float = 0.6


class GraphConsistencyChecking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphConsistencyCheckingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        entity_claims: dict[str, list[float]] = defaultdict(list)
        for ctx in contexts:
            entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

            for e in entities:
                entity_claims[e].append(ctx.relevance_score)

                for ctx in contexts:
                    entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ctx.content))

                    if not entities:
                        continue

                        consistencies = []

                        for e in entities:
                            scores = entity_claims.get(e, [])

                            if len(scores) > 1:
                                consistencies.append(1.0 - (max(scores) - min(scores)))

                                if consistencies:
                                    consistency = sum(consistencies) / len(consistencies)

                                    ctx.relevance_score = round(
                                        (1.0 - self.cfg.consistency_threshold) * ctx.relevance_score
                                        + self.cfg.consistency_threshold * consistency,
                                        4,
                                    )

        return contexts
