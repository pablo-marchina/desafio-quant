from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class SliceLevelRegressionReport:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            slices: dict[str, list[float]] = {}
            for ctx in contexts:
                slice_key = self._assign_slice(ctx)

                if slice_key not in slices:
                    slices[slice_key] = []

                    slices[slice_key].append(ctx.relevance_score)

                    slice_means = {k: sum(v) / max(len(v), 1) for k, v in slices.items()}
                    overall_mean = sum(ctx.relevance_score for ctx in contexts) / max(len(contexts), 1)

                    for ctx in contexts:
                        slice_key = self._assign_slice(ctx)

                        slice_mean = slice_means.get(slice_key, overall_mean)

                        if slice_mean < overall_mean * 0.7:
                            ctx.relevance_score = round(ctx.relevance_score * 0.85, 4)

        return contexts

    @staticmethod
    def _assign_slice(ctx: RetrievedContext) -> str:
        if ctx.gap_types:
            return "_".join(ctx.gap_types)
        numbers = re.findall(r"\b\d+\b", ctx.content[:100])
        return "numeric" if numbers else "textual"
