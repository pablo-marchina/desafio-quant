from __future__ import annotations

from typing import Any

from src.rag.colbert import Colbert
from src.rag.schemas import RetrievedContext


class ColbertReranking(Colbert):
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return super().run(contexts, **kwargs)
