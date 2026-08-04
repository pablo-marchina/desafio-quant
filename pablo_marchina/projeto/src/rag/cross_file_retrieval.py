"""cross-file retrieval

Hypothesis: Evaluate whether cross-file retrieval improves final product output without paid dependency.
Category: 8.48 Software V and V
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CrossFileRetrieval:
    """cross-file retrieval"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_file_index", None):
            self._file_index: dict[str, set[str]] = {}

        for ctx in contexts:
            for other in contexts:
                if other.source_id != ctx.source_id:
                    common = set(ctx.content.split()) & set(other.content.split())

                    if len(common) > 5:
                        pair = tuple(sorted([ctx.source_id, other.source_id]))

                        self._file_index[str(pair)] = set(common)

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
