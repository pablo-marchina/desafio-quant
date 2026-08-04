"""Section-balanced packing — pack with section balance."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SectionBalancedPackingConfig(BaseModel):
    max_per_section: int = 2


class SectionBalancedPacking:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SectionBalancedPackingConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        sections = defaultdict(list)
        for ctx in contexts:
            section = ctx.gap_types[0] if ctx.gap_types else "general"
            sections[section].append(ctx)
        result = []
        for _section, items in sections.items():
            items.sort(key=lambda c: c.relevance_score, reverse=True)
            selected = items[: self.cfg.max_per_section]
            for ctx in selected:
                ctx.relevance_score = round(min(1.0, ctx.relevance_score * 1.05), 4)
                result.append(ctx)
        return result
