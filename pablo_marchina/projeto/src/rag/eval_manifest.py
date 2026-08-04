from __future__ import annotations

import time
from typing import Any

from src.rag.schemas import RetrievedContext


class EvalManifest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._eval_history: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            manifest_entry: dict[str, Any] = {
                "timestamp": time.time(),
                "eval_name": self.__class__.__name__,
                "num_contexts": len(contexts),
                "avg_score": round(sum(c.relevance_score for c in contexts) / max(len(contexts), 1), 4),
                "context_ids": [c.chunk_id for c in contexts],
            }
            self._eval_history.append(manifest_entry)
            for ctx in contexts:
                ctx.relevance_score = round(ctx.relevance_score * 1.01, 4)

        return contexts
