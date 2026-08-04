"""code ownership metadata

Hypothesis: Evaluate whether code ownership metadata improves final product output without paid dependency.
Category: 8.38 Source Acquisition and Freshness
Expected runtime use: candidate_or_supporting_governance
"""

from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class CodeOwnershipMetadata:
    """code ownership metadata"""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not getattr(self, "_ownership", None):
            self._ownership: dict[str, str] = {}

        for ctx in contexts:
            path = ctx.source_id

            owner = "unknown"

            if "/" in path:
                parts = path.split("/")

                for p in parts:
                    if p.endswith("_owner") or p.startswith("team_"):
                        owner = p

                        break

            self._ownership[path] = owner

            ctx.relevance_score = min(1.0, ctx.relevance_score + 0.02)

        return contexts
