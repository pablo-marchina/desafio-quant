"""hash of final report

Hypothesis: Evaluate whether hash of final report improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HashOfFinalReport:
    """hash of final report"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import hashlib
        import json

        report_content = json.dumps({"contexts": [(c.chunk_id, c.relevance_score) for c in contexts]}, sort_keys=True)

        if not getattr(self, "_report_hash", None):
            self._report_hash: str = ""

        self._report_hash = hashlib.sha256(report_content.encode()).hexdigest()

        return contexts
