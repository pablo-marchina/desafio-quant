"""GraphRAG groundedness annotation — annotate groundedness."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class GraphragGroundednessAnnotationConfig(BaseModel):
    groundedness_bonus: float = 0.15


class GraphragGroundednessAnnotation:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = GraphragGroundednessAnnotationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            citations = len(re.findall(r"\[.*?\]|\(https?://[^\s]+\)", ctx.content))

            numbers = len(re.findall(r"\d+[\.\d]*(?:\s*%|\s*\$|\s*[A-Za-z]*\b)", ctx.content))

            groundedness = min(1.0, (citations + numbers) * 0.05)

            if groundedness > 0.3:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score + self.cfg.groundedness_bonus), 4)

        return contexts
