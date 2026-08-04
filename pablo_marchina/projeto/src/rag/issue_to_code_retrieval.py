"""issue-to-code retrieval

Hypothesis: Evaluate whether issue-to-code retrieval improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class IssueToCodeRetrieval:
    """issue-to-code retrieval"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        issue_keywords = {"issue", "bug", "feature request", "improvement", "task", "story", "ticket", "#"}

        for ctx in contexts:
            words = set(ctx.content.lower().split())

            overlap = len(words & issue_keywords)

            if overlap:
                ctx.relevance_score = min(1.0, ctx.relevance_score + overlap * 0.04)

        return contexts
