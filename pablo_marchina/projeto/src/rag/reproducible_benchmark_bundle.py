from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ReproducibleBenchmarkBundle:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import hashlib
        import json

        data = json.dumps([c.model_dump() for c in contexts], sort_keys=True, default=str)
        bundle_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
        for ctx in contexts:
            ctx.content = f"[BENCHMARK_HASH:{bundle_hash}] " + ctx.content

        return contexts
