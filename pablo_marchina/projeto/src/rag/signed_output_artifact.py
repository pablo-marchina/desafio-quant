from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class SignedOutputArtifact:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        import hashlib
        import json

        context_data = json.dumps([c.model_dump() for c in contexts], sort_keys=True, default=str)
        signature = hashlib.sha256(context_data.encode()).hexdigest()
        for ctx in contexts:
            ctx.content = f"[SIGNED:{signature[:12]}] " + ctx.content

        return contexts
