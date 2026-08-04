from __future__ import annotations

from typing import Any

from src.rag.schemas import RetrievedContext

_ENTITY_TYPE_HINTS = [
    "corporation",
    "inc",
    "llc",
    "ltd",
    "gmbh",
    "sa",
    "university",
    "institute",
    "research",
    "lab",
    "startup",
    "company",
    "enterprise",
    "group",
]


class SameNameEntityConfusionTest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        titles_seen: dict[str, list[int]] = {}
        for i, ctx in enumerate(contexts):
            key = ctx.title.lower().strip()

            titles_seen.setdefault(key, []).append(i)

            for title, indices in titles_seen.items():
                if len(indices) < 2:
                    continue

                    for idx in indices:
                        ctx = contexts[idx]

                        confusion_risk = self._assess_confusion_risk(ctx, title)

                        if confusion_risk > 0:
                            ctx.relevance_score = round(max(0.0, ctx.relevance_score - confusion_risk), 4)

        return contexts

    def _assess_confusion_risk(self, ctx: RetrievedContext, title: str) -> float:
        risk = 0.0
        if ctx.url:
            if "wikipedia" in ctx.url.lower():
                risk += 0.1
        content_lower = ctx.content.lower()
        entity_hints_found = sum(1 for hint in _ENTITY_TYPE_HINTS if hint in content_lower)
        if entity_hints_found == 0:
            risk += 0.2
        if len(ctx.content) < 100:
            risk += 0.2
        return min(risk, 0.5)
