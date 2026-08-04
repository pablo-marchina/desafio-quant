"""conclusion after evidence synthesis

Hypothesis: Evaluate whether conclusion after evidence synthesis improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ConclusionAfterEvidenceSynthesis:
    """conclusion after evidence synthesis"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            evidence_markers = sum(
                1
                for w in ["therefore", "conclusion", "in summary", "thus", "hence", "overall", "finally"]
                if w.lower() in ctx.content.lower()
            )

            if evidence_markers:
                ctx.relevance_score = min(1.0, ctx.relevance_score + evidence_markers * 0.03)

            else:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.02)

        return contexts
