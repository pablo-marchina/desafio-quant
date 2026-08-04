from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_PROFANITY_PATTERNS = re.compile(
    r"\b(fuck|shit|ass|bitch|damn|crap|dick|piss|bastard|slut|whore)\b",
    re.IGNORECASE,
)

_NSFW_TERMS = [
    "nsfw",
    "xxx",
    "porn",
    "sex",
    "nude",
    "explicit content",
]

_PII_PATTERNS = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    r"|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
    r"|\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"
)


class Openguardrails:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._flagged_threshold = int(self.config.get("flagged_threshold", 1))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            content_lower = ctx.content.lower()

            flag_count = 0

            if _PROFANITY_PATTERNS.search(ctx.content):
                flag_count += 1

                for term in _NSFW_TERMS:
                    if term in content_lower:
                        flag_count += 1

                        break

                        if _PII_PATTERNS.search(ctx.content):
                            flag_count += 1

                            if flag_count >= self._flagged_threshold:
                                penalty = flag_count * 0.2

                                ctx.relevance_score = round(max(0.0, ctx.relevance_score - penalty), 4)

        return contexts
