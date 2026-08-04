"""schema stress tests

Hypothesis: Evaluate whether schema stress tests improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SchemaStressTests:
    """schema stress tests"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        required_fields = ["chunk_id", "source_id", "title", "content", "product"]
        for ctx in contexts:
            missing = [f for f in required_fields if not getattr(ctx, f, None)]

            if missing:
                ctx.relevance_score = max(0.0, ctx.relevance_score - len(missing) * 0.08)

        return contexts
