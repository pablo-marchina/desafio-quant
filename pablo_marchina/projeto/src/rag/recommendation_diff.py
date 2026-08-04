from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RecommendationDiff:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._prev_scores: dict[str, float] = {}
        self._diffs: list[dict[str, Any]] = []

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        threshold = self.config.get("diff_threshold", 0.15)
        for ctx in contexts:
            prev = self._prev_scores.get(ctx.chunk_id, ctx.relevance_score)

            delta = ctx.relevance_score - prev

            if abs(delta) > threshold:
                self._diffs.append(
                    {
                        "id": ctx.chunk_id,
                        "delta": round(delta, 4),
                        "from": round(prev, 4),
                        "to": round(ctx.relevance_score, 4),
                    }
                )

                ctx.relevance_score = max(0.0, min(1.0, ctx.relevance_score + (0.05 if delta > 0 else -0.05)))

                self._prev_scores[ctx.chunk_id] = ctx.relevance_score

                self._diffs = self._diffs[-200:]
        return contexts
