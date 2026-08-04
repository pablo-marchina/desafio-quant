"""preference memory

Hypothesis: Evaluate whether preference memory improves final product output without paid dependency.
Category: 8.43 Memory and Negative Learning
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class PreferenceMemory:
    """preference memory"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_preferences", None):
            self._preferences: dict[str, float] = {}

        source_type_bonus = {"official": 0.2, "academic": 0.15, "nvidia": 0.25}

        for ctx in contexts:
            for s_type, bonus in source_type_bonus.items():
                if s_type in ctx.source_id.lower() or s_type in ctx.title.lower():
                    ctx.relevance_score = min(1.0, ctx.relevance_score + bonus)

            pref_key = ctx.source_id.split("_")[0] if "_" in ctx.source_id else ctx.source_id

            ctx.relevance_score = min(1.0, ctx.relevance_score + self._preferences.get(pref_key, 0.0))

        return contexts
