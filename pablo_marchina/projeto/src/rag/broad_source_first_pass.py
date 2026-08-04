"""broad source first pass

Hypothesis: Evaluate whether broad source first pass improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class BroadSourceFirstPass:
    """broad source first pass"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            if ctx.url:
                domain = ctx.url.split("/")[2] if "://" in ctx.url else ctx.url.split("/")[0]

                tld = domain.split(".")[-1] if "." in domain else ""

                if tld in {"com", "org", "net", "io", "ai"}:
                    ctx.relevance_score = min(1.0, ctx.relevance_score + 0.05)

        return contexts
