"""Selected-document full read — selected full reads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SelectedDocumentFullReadConfig(BaseModel):
    top_n: int = 3


class SelectedDocumentFullRead:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SelectedDocumentFullReadConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scored = sorted(contexts, key=lambda c: c.relevance_score, reverse=True)
        top = scored[: self.cfg.top_n]
        for ctx in top:
            ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.1), 4)
        return top + scored[self.cfg.top_n :]
