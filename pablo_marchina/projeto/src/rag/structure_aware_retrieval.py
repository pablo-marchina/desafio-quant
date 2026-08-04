from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext

_HEADING_PATTERN = re.compile(r"^(#{1,6}\s+|\w+[.:]\s+|[A-Z][^.]*\n[-=]+\s*$)", re.MULTILINE)

_SECTION_SIGNALS = [
    "introduction",
    "overview",
    "prerequisites",
    "installation",
    "configuration",
    "usage",
    "api",
    "examples",
    "troubleshooting",
    "faq",
    "see also",
    "references",
    "appendix",
]


class StructureAwareRetrievalConfig(BaseModel):
    enabled: bool = True
    boost_for_structured: float = 0.1
    boost_for_heading_match: float = 0.15


class StructureAwareRetrieval:
    def __init__(self, config: Any | None = None) -> None:
        self.config = StructureAwareRetrievalConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query: str = kwargs.get("query", "")
        query_lower = query.lower()
        for ctx in contexts:
            boost = 0.0

            if self._has_structure(ctx.content):
                boost += self.config.boost_for_structured

                heading = self._extract_heading(ctx.content)

                if heading and any(signal in query_lower for signal in heading.lower().split()):
                    boost += self.config.boost_for_heading_match

                    if boost > 0.0:
                        ctx.relevance_score = round(min(ctx.relevance_score + boost, 1.0), 4)

        return contexts

    @staticmethod
    def _has_structure(content: str) -> bool:
        if _HEADING_PATTERN.search(content):
            return True
        lines = content.split("\n")
        if len(lines) >= 5:
            non_empty = [ln for ln in lines if ln.strip()]
            if len(non_empty) >= 5:
                return True
        return False

    @staticmethod
    def _extract_heading(content: str) -> str:
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if stripped.startswith("=") or stripped.startswith("-"):
                continue
            if stripped and len(stripped) < 100 and stripped[0].isupper():
                return stripped
        return ""
