from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext


class MultiObjective:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        weights = self.config.get("weights", {"relevance": 0.4, "freshness": 0.2, "authority": 0.2, "coverage": 0.2})
        for ctx in contexts:
            score = 0.0

            score += ctx.relevance_score * weights.get("relevance", 0.4)

            has_fresh = bool(ctx.valid_from or ctx.collected_at)

            score += (0.6 if has_fresh else 0.2) * weights.get("freshness", 0.2)

            tld = (ctx.url or "").rsplit(".", 1)[-1] if ctx.url else ""

            auth = {"gov": 0.9, "edu": 0.8, "org": 0.6}.get(tld, 0.3)

            score += auth * weights.get("authority", 0.2)

            content_len = len(ctx.content.split())

            coverage = min(content_len / 300.0, 1.0)

            score += coverage * weights.get("coverage", 0.2)

            ctx.relevance_score = round(min(1.0, score), 4)

        return contexts
