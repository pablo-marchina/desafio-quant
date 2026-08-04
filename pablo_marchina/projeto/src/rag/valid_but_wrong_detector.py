"""valid-but-wrong detector

Hypothesis: Evaluate whether valid-but-wrong detector improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ValidButWrongDetector:
    """valid-but-wrong detector"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_contradiction_map", None):
            self._contradiction_map: dict[str, list[str]] = {}

        conflicting_pairs = [
            ("guaranteed", "may not"),
            ("always", "sometimes"),
            ("all", "some"),
            ("must", "optional"),
            ("required", "recommended"),
        ]

        for ctx in contexts:
            text_lower = ctx.content.lower()

            for a, b in conflicting_pairs:
                if a in text_lower and b in text_lower:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.08)

        return contexts
