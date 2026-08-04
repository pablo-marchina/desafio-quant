"""hash of evidence set

Hypothesis: Evaluate whether hash of evidence set improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class HashOfEvidenceSet:
    """hash of evidence set"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import hashlib

        evidence_content = "".join(sorted(c.content[:100] for c in contexts))

        evidence_hash = hashlib.sha256(evidence_content.encode()).hexdigest()

        if not getattr(self, "_evidence_hashes", None):
            self._evidence_hashes: list[str] = []

        self._evidence_hashes.append(evidence_hash)

        self._evidence_hashes = self._evidence_hashes[-100:]

        return contexts
