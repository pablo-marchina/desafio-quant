from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceTypeErrorSlices:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            source_types: dict[str, list[float]] = {}
            for ctx in contexts:
                s_type = ctx.source_id

                if s_type not in source_types:
                    source_types[s_type] = []

                    source_types[s_type].append(ctx.relevance_score)

                    type_means = {t: sum(s) / max(len(s), 1) for t, s in source_types.items()}
                    overall_mean = sum(ctx.relevance_score for ctx in contexts) / max(len(contexts), 1)
                    for ctx in contexts:
                        type_mean = type_means.get(ctx.source_id, overall_mean)

                        if type_mean < overall_mean * 0.6:
                            ctx.relevance_score = round(ctx.relevance_score * 0.8, 4)

        return contexts
