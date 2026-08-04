from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceDeletionStressTest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_deleted_sources", None):
            self._deleted_sources: set[str] = set()

            for ctx in list(contexts):
                if ctx.source_id in self._deleted_sources:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.5)

                    ctx.is_active = False

                    if kwargs.get("delete_source") == ctx.source_id:
                        self._deleted_sources.add(ctx.source_id)

        return contexts
