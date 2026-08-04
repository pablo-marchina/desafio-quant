"""Report composer agent — compose structured report from contexts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class ReportComposerAgentConfig(BaseModel):
    max_sections: int = 5


class ReportComposerAgent:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = ReportComposerAgentConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        sections = defaultdict(list)
        for ctx in contexts:
            key = ctx.gap_types[0] if ctx.gap_types else "general"
            sections[key].append(ctx)
        result = []
        for _gap, items in sections.items():
            items.sort(key=lambda x: x.relevance_score, reverse=True)
            top = items[: max(1, self.cfg.max_sections // max(1, len(sections)))]
            result.extend(top)
        return result
