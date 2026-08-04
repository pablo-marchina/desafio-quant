from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_LOOKALIKE_TLDS = [".xyz", ".top", ".loan", ".click", ".review", ".work", ".gq", ".ml", ".tk", ".cf"]
_TRUST_ABUSE_PHRASES = [
    "official partner",
    "certified by",
    "verified by",
    "trusted by",
    "recommended by",
    "featured on",
    "as seen on",
    "in partnership with",
]


class SourceTrustAttackSimulation:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            attack_score = self._simulate_attack(ctx)

            if attack_score > 0:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - attack_score * 0.3), 4)

        return contexts

    def _simulate_attack(self, ctx: RetrievedContext) -> float:
        score = 0.0
        if ctx.url:
            url_lower = ctx.url.lower()
            for tld in _LOOKALIKE_TLDS:
                if url_lower.endswith(tld):
                    score += 0.4
                    break
            if re.search(r"\d{4,}", url_lower):
                score += 0.2
        content_lower = ctx.content.lower()
        for phrase in _TRUST_ABUSE_PHRASES:
            if phrase in content_lower:
                score += 0.15
        return min(score, 1.0)
