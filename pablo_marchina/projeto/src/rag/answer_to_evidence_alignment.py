"""_answer-to-evidence alignment_

Hypothesis: Evaluate whether answer-to-evidence alignment improves final product output without paid dependency.
Category: 8.33 Claim Verification and Groundedness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class AnswerToEvidenceAlignment:
    """_answer-to-evidence alignment_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
