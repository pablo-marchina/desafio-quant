"""negative lessons memory

Hypothesis: Evaluate whether negative lessons memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class NegativeLessonsMemory:
    """negative lessons memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_negative_lessons", None):
            self._negative_lessons: list[str] = []

        for ctx in contexts:
            for lesson in self._negative_lessons:
                if lesson.lower() in ctx.content.lower():
                    ctx.relevance_score = max(0.0, ctx.relevance_score - 0.12)

        if "negative_lesson" in kwargs:
            self._negative_lessons.append(str(kwargs["negative_lesson"]))

        return contexts
