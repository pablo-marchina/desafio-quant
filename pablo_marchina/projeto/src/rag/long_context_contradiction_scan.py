"""Long-context contradiction scan — scan for contradictions in long context."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class LongContextContradictionScanConfig(BaseModel):
    contradiction_penalty: float = 0.15


class LongContextContradictionScan:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = LongContextContradictionScanConfig.model_validate(config or {})

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

                    contradictions = 0

                    for e in entities:
                        scores = entity_claims.get(e, [])

                        if len(scores) > 1 and max(scores) - min(scores) > 0.4:
                            contradictions += 1

                            penalty = contradictions * self.cfg.contradiction_penalty

                            ctx.relevance_score = round(max(0.0, ctx.relevance_score - penalty), 4)

        return contexts
