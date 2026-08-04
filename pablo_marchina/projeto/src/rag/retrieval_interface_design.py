"""_retrieval interface design_

Hypothesis: Evaluate whether retrieval interface design improves final product output without paid dependency.
Category: 8.49 Formal Agentic RAG Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RetrievalInterfaceDesign:
    """_retrieval interface design_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._interface_log: list[dict] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        expected_fields = {"chunk_id", "source_id", "title", "content", "product", "relevance_score"}
        for ctx in contexts:
            present = sum(1 for f in expected_fields if getattr(ctx, f, None) is not None)

            completeness = present / len(expected_fields)

            has_content = bool(ctx.content and len(ctx.content) > 20)

            has_provenance = bool(ctx.url or ctx.source_id)

            design_score = completeness * 0.4 + has_content * 0.3 + has_provenance * 0.3

            self._interface_log.append(
                {
                    "chunk_id": ctx.chunk_id,
                    "completeness": round(completeness, 3),
                    "design_score": round(design_score, 3),
                }
            )

            self._interface_log = self._interface_log[-200:]

            ctx.relevance_score = min(1.0, ctx.relevance_score * 0.6 + design_score * 0.4)

        return contexts
