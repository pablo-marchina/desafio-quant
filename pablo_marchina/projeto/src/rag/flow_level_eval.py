from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FlowLevelEval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._flow_metrics: dict[str, list[float]] = {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            for gap in ctx.gap_types:
                if gap not in self._flow_metrics:
                    self._flow_metrics[gap] = []

                    self._flow_metrics[gap].append(ctx.relevance_score)

                    for ctx in contexts:
                        for gap in ctx.gap_types:
                            gap_scores = self._flow_metrics.get(gap, [ctx.relevance_score])

                            avg_gap = sum(gap_scores) / max(len(gap_scores), 1)

                            if ctx.relevance_score < avg_gap * 0.6:
                                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
