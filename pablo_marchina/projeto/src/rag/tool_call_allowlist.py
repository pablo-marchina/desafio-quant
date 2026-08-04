"""tool call allowlist

Hypothesis: Evaluate whether tool call allowlist improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolCallAllowlist:
    """tool call allowlist"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_allowlist", None):
            self._allowlist: set[str] = set(
                self.config.get(
                    "allowed_tools",
                    [
                        "search",
                        "retrieve",
                        "embed",
                        "rerank",
                        "generate",
                    ],
                )
            )

        for ctx in contexts:
            content_lower = ctx.content.lower()

            allowed_hits = sum(1 for t in self._allowlist if t in content_lower)

            if allowed_hits:
                ctx.relevance_score = min(1.0, ctx.relevance_score + allowed_hits * 0.03)

        return contexts
