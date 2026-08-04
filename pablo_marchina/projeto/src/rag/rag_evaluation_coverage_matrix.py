from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class RagEvaluationCoverageMatrix:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

        topics: dict[str, list[RetrievedContext]] = {}
        for ctx in contexts:
            for term in re.findall(r"\b[A-Z][a-z]+\b", ctx.content):
                if len(term) > 3:
                    if term not in topics:
                        topics[term] = []

                        topics[term].append(ctx)

                        covered_topics = sum(1 for t_list in topics.values() if len(t_list) >= 2)
                        total_topics = max(len(topics), 1)
                        coverage = covered_topics / total_topics
                        for ctx in contexts:
                            ctx.relevance_score = round(ctx.relevance_score * (0.5 + 0.5 * coverage), 4)

        return contexts
