from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class BenchmarkDatasetVersioning:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import hashlib
        import json

        data = json.dumps([c.chunk_id for c in contexts], sort_keys=True)
        version_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
        for ctx in contexts:
            ctx.version = f"v_{version_hash[:8]}"

        return contexts
