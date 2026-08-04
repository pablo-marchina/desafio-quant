from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class EvidenceManifest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._manifests: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scores = [c.relevance_score for c in contexts]
        manifest: dict[str, Any] = {
            "num_contexts": len(contexts),
            "avg_score": round(sum(scores) / max(len(scores), 1), 4),
            "max_score": max(scores) if scores else 0.0,
            "min_score": min(scores) if scores else 0.0,
            "context_ids": [c.chunk_id for c in contexts],
        }
        self._manifests.append(manifest)
        self._manifests = self._manifests[-200:]
        return contexts
