"""document-to-test traceability

Hypothesis: Evaluate whether document-to-test traceability improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DocumentToTestTraceability:
    """document-to-test traceability"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_traceability", None):
            self._traceability: dict[str, list[str]] = {}

        for ctx in contexts:
            doc_id = ctx.source_id

            if doc_id not in self._traceability:
                self._traceability[doc_id] = []

            for other in contexts:
                if other.source_id != doc_id and other.chunk_id not in self._traceability[doc_id]:
                    self._traceability[doc_id].append(other.chunk_id)

            trace_count = len(self._traceability.get(doc_id, []))

            if trace_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + trace_count * 0.02)

        return contexts
