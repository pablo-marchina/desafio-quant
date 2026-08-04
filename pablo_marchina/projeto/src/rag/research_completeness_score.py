"""research completeness score

Hypothesis: Evaluate whether research completeness score improves final product output without paid dependency.
Category: 8.45 Failure Transparency and Completeness Control
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ResearchCompletenessScore:
    """research completeness score"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_required_topics", None):
            self._required_topics: set[str] = set()

        if kwargs.get("topics"):
            self._required_topics = set(str(kwargs["topics"]).split(","))

        covered = set()

        for ctx in contexts:
            text_lower = ctx.content.lower()

            for t in self._required_topics:
                if t.strip().lower() in text_lower:
                    covered.add(t.strip())

        coverage = len(covered) / max(len(self._required_topics), 1)

        for ctx in contexts:
            if coverage < 0.5:
                ctx.relevance_score = max(0.0, ctx.relevance_score - 0.05)

        return contexts
