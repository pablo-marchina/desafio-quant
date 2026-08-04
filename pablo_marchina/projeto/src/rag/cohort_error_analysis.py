from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CohortErrorAnalysis:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            cohorts: dict[str, list[float]] = {}
            for ctx in contexts:
                cohort = next(iter(ctx.gap_types), ctx.product) or "unknown"

                if cohort not in cohorts:
                    cohorts[cohort] = []

                    cohorts[cohort].append(ctx.relevance_score)

                    cohort_stats: dict[str, dict[str, float]] = {}
                    for c, scores in cohorts.items():
                        cohort_stats[c] = {
                            "mean": sum(scores) / max(len(scores), 1),
                            "std": (
                                sum((s - sum(scores) / max(len(scores), 1)) ** 2 for s in scores) / max(len(scores), 1)
                            )
                            ** 0.5,
                        }

                        for ctx in contexts:
                            cohort = next(iter(ctx.gap_types), ctx.product) or "unknown"

                            stats = cohort_stats.get(cohort, {"mean": 0.5, "std": 0.2})

                            lower = stats["mean"] - stats["std"]

                            if ctx.relevance_score < lower:
                                ctx.relevance_score = round(lower, 4)

        return contexts
