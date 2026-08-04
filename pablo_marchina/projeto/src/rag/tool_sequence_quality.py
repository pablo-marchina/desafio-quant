"""tool sequence quality

Hypothesis: Evaluate whether tool sequence quality improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolSequenceQuality:
    """tool sequence quality"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        sequence_markers = ["first", "then", "next", "finally", "after", "before"]
        for ctx in contexts:
            seq_count = sum(1 for m in sequence_markers if m in ctx.content.lower())

            if seq_count >= 2:
                ctx.relevance_score = min(1.0, ctx.relevance_score + seq_count * 0.03)

        return contexts
