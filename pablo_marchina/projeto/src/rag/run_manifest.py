from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RunManifest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._runs: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        run_entry: dict[str, Any] = {
            "run_id": kwargs.get("run_id", "unknown"),
            "num_contexts": len(contexts),
            "avg_score": round(sum(c.relevance_score for c in contexts) / max(len(contexts), 1), 4),
            "params": {k: str(v) for k, v in kwargs.items() if k != "run_id"},
        }
        self._runs.append(run_entry)
        self._runs = self._runs[-200:]
        return contexts
