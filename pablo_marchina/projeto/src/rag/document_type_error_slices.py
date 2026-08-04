from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DocumentTypeErrorSlices:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            doc_types: dict[str, list[float]] = {}
            for ctx in contexts:
                d_type = ctx.product

                if d_type not in doc_types:
                    doc_types[d_type] = []

                    doc_types[d_type].append(ctx.relevance_score)

                    for ctx in contexts:
                        scores = doc_types.get(ctx.product, [])

                        if len(scores) >= 3:
                            mean = sum(scores) / len(scores)

                            variance = sum((s - mean) ** 2 for s in scores) / len(scores)

                            if variance > 0.1:
                                ctx.relevance_score = round(ctx.relevance_score * 0.85, 4)

        return contexts
