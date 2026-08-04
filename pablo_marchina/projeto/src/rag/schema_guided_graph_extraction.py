"""Schema-guided graph extraction — schema-guided extraction."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievedContext


class SchemaGuidedGraphExtractionConfig(BaseModel):
    extraction_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
            r"\b[A-Z]{2,}\b",
        ]
    )


class SchemaGuidedGraphExtraction:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SchemaGuidedGraphExtractionConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            extracted = set()

            for pattern in self.cfg.extraction_patterns:
                extracted.update(re.findall(pattern, ctx.content))

                extraction_density = len(extracted) / max(1, len(set(ctx.content.split())))

                ctx.relevance_score = round(min(1.0, ctx.relevance_score + extraction_density * 0.2), 4)

        return contexts
