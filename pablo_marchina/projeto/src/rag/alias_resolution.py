"""alias resolution

Hypothesis: Evaluate whether alias resolution improves final product output without paid dependency.
Category: 8.50 Terminology and Domain Adaptation
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class AliasResolution:
    """alias resolution"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_aliases", None):
            self._aliases: dict[str, list[str]] = {
                "nvidia": ["nvda", "nvidia corp", "nvidia corporation", "green team"],
                "openai": ["open ai", "open-ai"],
                "startup": ["start-up", "start up", "new venture"],
            }

        for ctx in contexts:
            resolved = 0

            for canonical, alias_list in self._aliases.items():
                if canonical.lower() in ctx.content.lower():
                    resolved += 1

                for a in alias_list:
                    if a.lower() in ctx.content.lower():
                        resolved += 1

            if resolved:
                ctx.relevance_score = min(1.0, ctx.relevance_score + resolved * 0.015)

        return contexts
