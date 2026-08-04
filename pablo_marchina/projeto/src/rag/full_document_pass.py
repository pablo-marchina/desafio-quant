"""Full-document pass — full document retrieval."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class FullDocumentPassConfig(BaseModel):
    coverage_boost: float = 0.1


class FullDocumentPass:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = FullDocumentPassConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            source_coverage = Counter(ctx.source_id for ctx in contexts)
            for ctx in contexts:
                coverage = source_coverage.get(ctx.source_id, 1) / max(1, len(contexts))

                ctx.relevance_score = round(min(1.0, ctx.relevance_score + coverage * self.cfg.coverage_boost), 4)

        return contexts
