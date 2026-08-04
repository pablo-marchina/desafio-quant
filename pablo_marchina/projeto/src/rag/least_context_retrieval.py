"""_least-context retrieval_

Hypothesis: Evaluate whether least-context retrieval improves final product output.
Category: 8.5 RAG/retrieval techniques
Expected runtime use: TBD_BY_RUNTIME_REVIEW
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class LeastContextRetrieval:
    """_least-context retrieval_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
