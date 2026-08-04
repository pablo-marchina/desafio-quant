from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ModelManifest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._manifests: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        manifest: dict[str, Any] = {
            "model": kwargs.get("model", "unknown"),
            "provider": kwargs.get("provider", "unknown"),
            "num_contexts": len(contexts),
            "avg_score": round(sum(c.relevance_score for c in contexts) / max(len(contexts), 1), 4),
        }
        self._manifests.append(manifest)
        self._manifests = self._manifests[-100:]
        return contexts
