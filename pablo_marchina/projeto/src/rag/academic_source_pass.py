"""academic source pass

Hypothesis: Evaluate whether academic source pass improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class AcademicSourcePass:
    """academic source pass"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        academic_domains = [
            ".edu",
            ".ac.",
            "arxiv.org",
            "scholar.google",
            "ieee.org",
            "acm.org",
            "springer.com",
            "sciencedirect.com",
        ]

        for ctx in contexts:
            url_lower = (ctx.url or "").lower()

            if any(d in url_lower for d in academic_domains):
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.2)

        return contexts
