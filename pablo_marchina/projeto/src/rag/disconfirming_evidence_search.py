"""_disconfirming evidence search_

Hypothesis: Evaluate whether disconfirming evidence search improves final product output without paid dependency.
Category: 8.31 Advanced Retrieval and Evidence Ranking
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class DisconfirmingEvidenceSearch:
    """_disconfirming evidence search_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
