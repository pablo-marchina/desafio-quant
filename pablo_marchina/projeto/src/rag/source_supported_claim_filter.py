"""_source-supported claim filter_

Hypothesis: Evaluate whether source-supported claim filter improves final product output without paid dependency.
Category: 8.33 Claim Verification and Groundedness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SourceSupportedClaimFilter:
    """_source-supported claim filter_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
