"""case memory

Hypothesis: Evaluate whether case memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CaseMemory:
    """case memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_cases", None):
            self._cases: list[dict] = []

        for ctx in contexts:
            for c in self._cases:
                overlap = len(set(c.get("terms", [])) & set(ctx.content.lower().split()))

                if overlap > 2:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.03 * overlap)

        all_terms = list(set(w.lower().strip(".,!?;:") for c in contexts for w in c.content.split()[:20]))

        self._cases.append({"terms": all_terms})

        self._cases = self._cases[-50:]

        return contexts
