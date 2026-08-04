"""_meta-retrieval / router de retrievers_

Hypothesis: Evaluate whether meta-retrieval / router de retrievers improves final product output.
Category: 8.5 RAG/retrieval techniques
Expected runtime use: TBD_BY_RUNTIME_REVIEW
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MetaRetrievalRouterDeRetrievers:
    """_meta-retrieval / router de retrievers_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
