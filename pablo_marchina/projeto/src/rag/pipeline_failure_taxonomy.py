"""pipeline failure taxonomy

Hypothesis: Evaluate whether pipeline failure taxonomy improves final product output without paid dependency.
Category: 8.46 Decision Accountability
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PipelineFailureTaxonomy:
    """pipeline failure taxonomy"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_pipeline_failures", None):
            self._pipeline_failures: dict[str, list[str]] = {
                "ingestion": ["ingestion failed", "parse error", "corrupt"],
                "retrieval": ["empty result", "timeout", "connection error"],
                "generation": ["token limit", "refusal", "error response"],
            }

        for ctx in contexts:
            for _stage, signals in self._pipeline_failures.items():
                if any(s in ctx.content.lower() for s in signals):
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.06)

        return contexts
