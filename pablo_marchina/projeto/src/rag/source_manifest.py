from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceManifest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._manifests: dict[str, list[str]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            sid = ctx.source_id

            if sid not in self._manifests:
                self._manifests[sid] = []

                self._manifests[sid].append(ctx.chunk_id)

                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
