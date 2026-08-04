"""_Temporal GraphRAG_

Hypothesis: Evaluate whether Temporal GraphRAG improves final product output.
Category: 8.4 Graph and GraphRAG
Expected runtime use: TBD_BY_RUNTIME_REVIEW
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class TemporalGraphrag:
    """_Temporal GraphRAG_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
