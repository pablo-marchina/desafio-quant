from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RecommendationRationaleValidator:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        causal_markers = {"because", "therefore", "since", "due to", "as a result", "leads to", "causes"}
        for ctx in contexts:
            content = ctx.content.lower()

            has_causal = sum(1 for m in causal_markers if m in content)

            has_numbers = any(ch.isdigit() for ch in ctx.content)

            has_url = bool(ctx.url)

            rationale_score = min(has_causal * 0.15, 0.45) + (0.15 if has_numbers else 0) + (0.1 if has_url else 0)

            ctx.relevance_score = min(1.0, ctx.relevance_score * 0.5 + rationale_score * 0.5)

        return contexts
