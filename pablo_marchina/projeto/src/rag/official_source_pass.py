"""official source pass

Hypothesis: Evaluate whether official source pass improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class OfficialSourcePass:
    """official source pass"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        official_domains = ["nvidia.com", "nvidia.cn", "developer.nvidia.com", "docs.nvidia.com", "github.com/nvidia"]

        for ctx in contexts:
            url_lower = (ctx.url or "").lower()

            if any(d in url_lower for d in official_domains):
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.3)

        return contexts
