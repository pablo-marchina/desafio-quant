"""_refuting evidence span retrieval_

Hypothesis: Evaluate whether refuting evidence span retrieval improves final product output without paid dependency.
Category: 8.33 Claim Verification and Groundedness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RefutingEvidenceSpanRetrieval:
    """_refuting evidence span retrieval_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
