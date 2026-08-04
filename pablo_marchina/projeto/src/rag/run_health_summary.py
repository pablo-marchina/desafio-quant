from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RunHealthSummary:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        scores = [c.relevance_score for c in contexts]
        if not scores:
            return contexts

            summary = {
                "num_contexts": len(scores),
                "avg_score": round(sum(scores) / len(scores), 4),
                "max_score": max(scores),
                "min_score": min(scores),
                "coverage": len(set(c.source_id for c in contexts)) / max(len(contexts), 1),
            }
            for ctx in contexts:
                if ctx.relevance_score < summary["avg_score"] * 0.5:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
