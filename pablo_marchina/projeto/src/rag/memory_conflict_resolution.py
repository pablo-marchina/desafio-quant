"""memory conflict resolution

Hypothesis: Evaluate whether memory conflict resolution improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MemoryConflictResolution:
    """memory conflict resolution"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_memory_entries", None):
            self._memory_entries: dict[str, list[float]] = {}

        for ctx in contexts:
            key = ctx.chunk_id

            if key not in self._memory_entries:
                self._memory_entries[key] = []

            self._memory_entries[key].append(ctx.relevance_score)

            scores = self._memory_entries[key]

            if len(scores) > 1 and abs(scores[-1] - scores[-2]) > 0.3:
                ctx.relevance_score = sum(scores[-3:]) / min(len(scores[-3:]), 3)

        return contexts
