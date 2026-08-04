"""patch-style output

Hypothesis: Evaluate whether patch-style output improves final product output without paid dependency.
Category: 8.44 Output Versioning and Audit
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PatchStyleOutput:
    """patch-style output"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_patch_log", None):
            self._patch_log: list[dict] = []

        for ctx in contexts:
            self._patch_log.append({"chunk_id": ctx.chunk_id, "score_delta": ctx.relevance_score - 0.5})

        self._patch_log = self._patch_log[-500:]

        return contexts
