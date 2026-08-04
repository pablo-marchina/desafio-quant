from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ConfigManifest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._manifests: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        manifest: dict[str, Any] = {
            "config": {k: str(v) for k, v in self.config.items()},
            "num_contexts": len(contexts),
            "params": {k: str(v) for k, v in kwargs.items()},
        }
        self._manifests.append(manifest)
        self._manifests = self._manifests[-100:]
        return contexts
