from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceDiversityEnforcement:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._max_per_source = int(config.get("max_per_source", 2)) if isinstance(config, dict) else 2

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            source_count: dict[str, int] = {}
            for ctx in contexts:
                source_count[ctx.source_id] = source_count.get(ctx.source_id, 0) + 1

                for ctx in contexts:
                    if source_count.get(ctx.source_id, 0) > self._max_per_source:
                        penalty = self._max_per_source / source_count[ctx.source_id]

                        ctx.relevance_score = round(ctx.relevance_score * penalty, 4)

        return contexts
