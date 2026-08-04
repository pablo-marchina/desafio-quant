from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class FailureSliceAnalysis:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = float(config.get("threshold", 0.3)) if isinstance(config, dict) else 0.3

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            failures: list[RetrievedContext] = [c for c in contexts if c.relevance_score < self._threshold]
            failures_by_source: dict[str, int] = {}
            for f in failures:
                failures_by_source[f.source_id] = failures_by_source.get(f.source_id, 0) + 1

                if not failures_by_source:
                    return contexts

                    worst_source = max(failures_by_source, key=failures_by_source.get)
                    for ctx in contexts:
                        if ctx.source_id == worst_source:
                            ctx.relevance_score = round(ctx.relevance_score * 0.5, 4)

        return contexts
