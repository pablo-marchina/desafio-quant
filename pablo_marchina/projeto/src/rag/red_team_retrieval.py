from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class RedTeamRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._adversarial_chance = float(self.config.get("adversarial_chance", 0.1))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            weakness_score = self._assess_weakness(ctx)

            if weakness_score > 0:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - weakness_score * 0.2), 4)

        return contexts

    def _assess_weakness(self, ctx: RetrievedContext) -> float:
        score = 0.0
        content_lower = ctx.content.lower()
        if len(ctx.content) < 50:
            score += 0.3
        if "no evidence" in content_lower or "unclear" in content_lower:
            score += 0.2
        if "claim" in content_lower and "source" not in content_lower:
            score += 0.2
        if ctx.url and "wikipedia" in ctx.url.lower():
            score += 0.1
        if not ctx.url:
            score += 0.2
        return min(score, 1.0)
