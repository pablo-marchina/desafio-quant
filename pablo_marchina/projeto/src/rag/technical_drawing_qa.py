from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TECH_TERMS = re.compile(
    r"\b(dimension|tolerance|mm|cm|schematic|cad|blueprint|wiring|"
    r"circuit|connector|pinout|datasheet|specification|drawing)\b",
    re.I,
)
_DIMENSION = re.compile(r"\b\d+\s*(?:mm|cm|in|ft|m)\b", re.I)


class TechnicalDrawingQa:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            tech_terms = _TECH_TERMS.findall(ctx.content)
            dims = _DIMENSION.findall(ctx.content)
            if tech_terms or dims:
                ctx.content = f"[technical_drawing:terms={len(tech_terms)} dims={len(dims)}]\n{ctx.content}"
        return contexts
