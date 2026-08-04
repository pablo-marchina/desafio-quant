"""Source discovery agent — discover new sources from contexts."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SourceDiscoveryAgentConfig(BaseModel):
    max_suggestions: int = 3


class SourceDiscoveryAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SourceDiscoveryAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            urls = re.findall(r"https?://(?:www\.)?([^/\s]+)", ctx.content)

            orgs = re.findall(r"\b([A-Z][a-zA-Z]+(?:Inc|Corp|Ltd|LLC|SA|GmbH))\b", ctx.content)

            discovery_score = min(0.3, (len(urls) + len(orgs)) * 0.05)

            ctx.relevance_score = round(min(1.0, ctx.relevance_score + discovery_score), 4)

        return contexts
