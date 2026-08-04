from __future__ import annotations

from typing import Any

from src.rag.multi_query_retrieval import MultiQueryRetrieval
from src.rag.schemas import RetrievedContext


class MultiQuery(MultiQueryRetrieval):
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return super().run(contexts, **kwargs)
