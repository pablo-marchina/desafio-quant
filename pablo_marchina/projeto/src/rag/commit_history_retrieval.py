"""commit history retrieval

Hypothesis: Evaluate whether commit history retrieval improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CommitHistoryRetrieval:
    """commit history retrieval"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_commits", None):
            self._commits: list[dict] = []

        for ctx in contexts:
            commit_keywords = ["commit", "merge", "pr", "pull request", "fix", "feat", "update"]

            kw_count = sum(1 for k in commit_keywords if k.lower() in ctx.content.lower())

            if kw_count:
                ctx.relevance_score = min(1.0, ctx.relevance_score + kw_count * 0.03)

        return contexts
