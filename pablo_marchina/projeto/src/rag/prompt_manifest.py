from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PromptManifest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._manifests: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        manifest: dict[str, Any] = {
            "prompt_name": kwargs.get("prompt_name", "default"),
            "version": kwargs.get("version", "1.0"),
            "num_contexts": len(contexts),
            "avg_score": round(sum(c.relevance_score for c in contexts) / max(len(contexts), 1), 4),
            "params": {k: str(v) for k, v in kwargs.items() if k not in ("prompt_name", "version")},
        }
        self._manifests.append(manifest)
        self._manifests = self._manifests[-100:]
        return contexts
