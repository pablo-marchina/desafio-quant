"""source ranking

Hypothesis: Evaluate whether source ranking improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceRanking:
    """source ranking"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        tld_rank = {".gov": 0.9, ".edu": 0.85, ".org": 0.7, ".com": 0.6, ".io": 0.5}
        for ctx in contexts:
            if ctx.url:
                domain = ctx.url.split("/")[2] if "://" in ctx.url else "unknown"

                tld = "." + (domain.split(".")[-1] if "." in domain else "")

                tld_rank_val = tld_rank.get(tld, 0.5)

            else:
                tld_rank_val = 0.5

            ctx.relevance_score = min(1.0, ctx.relevance_score * 0.5 + tld_rank_val * 0.5)

        return contexts
