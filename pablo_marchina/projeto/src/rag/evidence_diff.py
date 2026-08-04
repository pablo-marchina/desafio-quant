"""_evidence diff_

Hypothesis: Evaluate whether evidence diff improves final product output without paid dependency.
Category: 8.44 Output Versioning, Audit Bundle and Report Compilation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class EvidenceDiff:
    """_evidence diff_"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return contexts
