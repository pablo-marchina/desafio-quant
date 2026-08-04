"""missing field detector

Hypothesis: Evaluate whether missing field detector improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MissingFieldDetector:
    """missing field detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        required_fields = self.config.get("required_fields", ["source_id", "content", "title"])
        for ctx in contexts:
            missing = 0

            for field in required_fields:
                if not getattr(ctx, field, None):
                    missing += 1

            if missing:
                ctx.relevance_score = max(0.0, ctx.relevance_score - missing * 0.1)

        return contexts
