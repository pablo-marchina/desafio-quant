"""_retrieve-then-read-full-document_

Hypothesis: Evaluate whether retrieve-then-read-full-document improves final product output without paid dependency.
Category: 8.37 Long-Context, Context Packing and Hierarchical Retrieval
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrieveThenReadFullDocument:
    """_retrieve-then-read-full-document_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._full_documents: dict[str, int] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        full_doc_threshold = self.config.get("full_doc_threshold", 500)
        for ctx in contexts:
            source = ctx.source_id

            content_len = len(ctx.content)

            is_full = content_len >= full_doc_threshold

            if source not in self._full_documents:
                self._full_documents[source] = 0

                if is_full:
                    self._full_documents[source] += 1

                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.08)

                else:
                    fragment_boost = min(self._full_documents.get(source, 0) * 0.02, 0.1)

                    ctx.relevance_score = min(1.0, ctx.relevance_score + fragment_boost)

        return contexts
