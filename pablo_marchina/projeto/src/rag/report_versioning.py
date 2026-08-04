"""report versioning

Hypothesis: Evaluate whether report versioning improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReportVersioning:
    """report versioning"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_report_versions", None):
            self._report_versions: list[dict] = []

        import hashlib
        import json

        version_hash = hashlib.md5(json.dumps([c.chunk_id for c in contexts], sort_keys=True).encode(), usedforsecurity=False).hexdigest()[:12]

        self._report_versions.append({"hash": version_hash, "count": len(contexts)})

        self._report_versions = self._report_versions[-100:]

        return contexts
