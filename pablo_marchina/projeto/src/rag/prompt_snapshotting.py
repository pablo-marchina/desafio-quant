"""prompt snapshotting

Hypothesis: Evaluate whether prompt snapshotting improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptSnapshotting:
    """prompt snapshotting"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_snapshots", None):
            self._snapshots: list[str] = []

        import hashlib

        snapshot = hashlib.md5("".join(c.content[:50] for c in contexts).encode(), usedforsecurity=False).hexdigest()[:12]

        self._snapshots.append(snapshot)

        self._snapshots = self._snapshots[-50:]

        return contexts
