from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RagReadinessScore:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            avg_relevance = sum(ctx.relevance_score for ctx in contexts) / max(len(contexts), 1)
            source_coverage = len({ctx.source_id for ctx in contexts}) / max(len(contexts), 1)
            has_provenance = sum(1 for ctx in contexts if ctx.url) / max(len(contexts), 1)
            score = 0.4 * avg_relevance + 0.3 * source_coverage + 0.3 * has_provenance
            for ctx in contexts:
                ctx.relevance_score = round(ctx.relevance_score * 0.5 + score * 0.5, 4)

        return contexts
