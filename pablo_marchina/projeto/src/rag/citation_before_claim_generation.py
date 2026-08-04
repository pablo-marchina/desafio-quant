"""citation before claim generation

Hypothesis: Evaluate whether citation before claim generation improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CitationBeforeClaimGeneration:
    """citation before claim generation"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            has_citation = bool(ctx.url) or any(c in ctx.content for c in ["[", "(", "doi:", "arxiv:"])

            if has_citation:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.15)

            else:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
