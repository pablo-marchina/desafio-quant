from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SystemLevelRagEvalMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            unique_sources = len({ctx.source_id for ctx in contexts})
            total_score = sum(ctx.relevance_score for ctx in contexts)
            avg_score = total_score / max(len(contexts), 1)
            source_diversity = unique_sources / max(len(contexts), 1)
            system_score = 0.4 * avg_score + 0.3 * source_diversity + 0.3 * (1.0 if unique_sources > 1 else 0.0)
            for ctx in contexts:
                ctx.relevance_score = round(ctx.relevance_score * 0.5 + system_score * 0.5, 4)

        return contexts
