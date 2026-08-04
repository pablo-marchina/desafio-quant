"""bad-answer memory

Hypothesis: Evaluate whether bad-answer memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class BadAnswerMemory:
    """bad-answer memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_bad_answers", None):
            self._bad_answers: list[str] = []

        for ctx in contexts:
            ctx_penalty = 0.0

            for ba in self._bad_answers:
                if ba.lower() in ctx.content.lower():
                    ctx_penalty -= 0.2

            ctx.relevance_score = max(0.0, ctx.relevance_score + ctx_penalty)

        if "bad_answer_phrase" in kwargs:
            self._bad_answers.append(str(kwargs["bad_answer_phrase"]))

        return contexts
