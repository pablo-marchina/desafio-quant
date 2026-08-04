"""Section-by-section generation — section-by-section gen."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SectionBySectionGenerationConfig(BaseModel):
    max_sections: int = 5


class SectionBySectionGeneration:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SectionBySectionGenerationConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        sections: OrderedDict[str, list[RetrievedContext]] = OrderedDict()
        for ctx in contexts:
            section = ctx.gap_types[0] if ctx.gap_types else "general"
            if section not in sections:
                sections[section] = []
            sections[section].append(ctx)
        result: list[RetrievedContext] = []
        for _section, items in list(sections.items())[: self.cfg.max_sections]:
            items.sort(key=lambda c: c.relevance_score, reverse=True)
            best = items[0]
            best.relevance_score = round(min(1.0, best.relevance_score * 1.1), 4)
            result.append(best)
        return result
