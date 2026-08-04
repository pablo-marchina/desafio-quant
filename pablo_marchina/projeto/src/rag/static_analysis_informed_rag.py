"""static analysis informed RAG

Hypothesis: Evaluate whether static analysis informed RAG improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class StaticAnalysisInformedRag:
    """static analysis informed RAG"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        analysis_markers = ["warning", "error", "lint", "type error", "undefined", "unused", "deprecated", "null"]

        for ctx in contexts:
            marker_count = sum(1 for m in analysis_markers if m.lower() in ctx.content.lower())

            if marker_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + marker_count * 0.04)

        return contexts
