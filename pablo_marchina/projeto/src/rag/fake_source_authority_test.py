from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_KNOWN_AUTHORITY_DOMAINS = [
    "nvidia.com",
    "nvidia.github.io",
    "developer.nvidia.com",
    "docs.nvidia.com",
    "arxiv.org",
    "ieee.org",
    "acm.org",
    "springer.com",
    "nature.com",
    "science.org",
    "mit.edu",
    "stanford.edu",
    "berkeley.edu",
    "gov",
    "edu",
]

_TYPOSQUAT_PATTERNS = [
    re.compile(r"nvid[a-z]a\.(com|org|net|io)"),
    re.compile(r"nvdia\.(com|org)"),
    re.compile(r"nvidiа\.com"),
    re.compile(r"nividia\.(com|org)"),
    re.compile(r"nviidia\.(com|org)"),
    re.compile(r"nvidia-"),
    re.compile(r"nvidia\.[a-z]{2,}$"),
]

_AUTHORITY_CLAIM_PATTERNS = [
    re.compile(r"according\s+to\s+(NVIDIA|Google|Microsoft|Amazon|Meta)", re.IGNORECASE),
    re.compile(r"as\s+reported\s+by\s+", re.IGNORECASE),
    re.compile(r"study\s+by\s+", re.IGNORECASE),
    re.compile(r"research\s+from\s+", re.IGNORECASE),
]


class FakeSourceAuthorityTest:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            risk = self._assess_authority_risk(ctx)

            if risk > 0:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - risk), 4)

        return contexts

    def _assess_authority_risk(self, ctx: RetrievedContext) -> float:
        risk = 0.0
        if ctx.url:
            url_lower = ctx.url.lower()
            for pattern in _TYPOSQUAT_PATTERNS:
                if pattern.search(url_lower):
                    risk += 0.5
                    break
            if not any(domain in url_lower for domain in _KNOWN_AUTHORITY_DOMAINS):
                risk += 0.2
        else:
            risk += 0.1
        content_lower = ctx.content.lower()
        for pattern in _AUTHORITY_CLAIM_PATTERNS:
            if pattern.search(content_lower):
                risk += 0.1
        return min(risk, 1.0)
