"""decision provenance

Hypothesis: Evaluate whether decision provenance improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DecisionProvenance:
    """decision provenance"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_provenance_log", None):
            self._provenance_log: list[dict] = []

        for ctx in contexts:
            self._provenance_log.append(
                {
                    "chunk_id": ctx.chunk_id,
                    "source_id": ctx.source_id,
                    "score": ctx.relevance_score,
                }
            )

        self._provenance_log = self._provenance_log[-500:]

        return contexts
