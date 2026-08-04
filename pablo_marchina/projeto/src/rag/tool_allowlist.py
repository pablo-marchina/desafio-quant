"""tool allowlist

Hypothesis: Evaluate whether tool allowlist improves final product output without paid dependency.
Category: 8.47 Tool/Flow/Prompt Governance
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class ToolAllowlist:
    """tool allowlist"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._allowlist: set[str] = set(
            self.config.get(
                "allowed_tools",
                [
                    "search",
                    "retrieve",
                    "embed",
                    "rerank",
                    "generate",
                    "read",
                ],
            )
        )

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            content_lower = ctx.content.lower()

            allowed_hits = sum(1 for t in self._allowlist if t in content_lower)

            disallowed = sum(1 for w in content_lower.split() if w.endswith("_tool") and w not in self._allowlist)

            if allowed_hits:
                ctx.relevance_score = min(1.0, ctx.relevance_score + allowed_hits * 0.02)

                if disallowed:
                    ctx.relevance_score = max(0.0, ctx.relevance_score - disallowed * 0.05)

        return contexts
