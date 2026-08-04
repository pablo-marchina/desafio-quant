"""tool retrieval

Hypothesis: Evaluate whether tool retrieval improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolRetrieval:
    """tool retrieval"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_tool_registry", None):
            self._tool_registry: dict[str, dict] = {}

        for ctx in contexts:
            tool_name = ctx.title.split()[0].lower() if ctx.title.split() else "unknown"

            if tool_name not in self._tool_registry:
                self._tool_registry[tool_name] = {"count": 0, "sources": []}

            self._tool_registry[tool_name]["count"] += 1

            self._tool_registry[tool_name]["sources"].append(ctx.source_id)

            if self._tool_registry[tool_name]["count"] > 0:
                ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
