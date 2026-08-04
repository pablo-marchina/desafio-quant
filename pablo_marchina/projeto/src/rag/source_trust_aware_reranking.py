from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RerankingConfig, RetrievedContext

_TRUSTED_DOMAINS = [
    "nvidia.com",
    "arxiv.org",
    "ieee.org",
    "acm.org",
    "scholar.google.com",
    "github.com",
    "docs.nvidia.com",
    "developer.nvidia.com",
]
_TRUST_PENALTY_WORDS = re.compile(r"\b(blog|forum|reddit|medium|wordpress|wix|unofficial|unverified)\b", re.I)


class SourceTrustAwareReranking:
    def __init__(self, config: Any | None = None) -> None:
        cfg = config or {}
        self.config = RerankingConfig.model_validate(cfg) if isinstance(cfg, dict) else cfg

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            url = ctx.url or ""
            is_trusted = any(d in url for d in _TRUSTED_DOMAINS)
            has_penalty = bool(_TRUST_PENALTY_WORDS.search(url + " " + ctx.title))
            delta = self.config.boost_known_source if is_trusted else 0.0
            delta += self.config.penalty_no_provenance if has_penalty else 0.0
            ctx.relevance_score = round(max(0.0, ctx.relevance_score + delta), 4)
        return sorted(contexts, key=lambda c: -c.relevance_score)
