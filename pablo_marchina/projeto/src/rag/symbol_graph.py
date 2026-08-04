"""Symbol graph — symbolic graph operations."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from src.rag.schemas import RetrievedContext


class SymbolGraphConfig(BaseModel):
    symbol_weight: float = 0.15


class SymbolGraph:
    def __init__(self, config: Any | None = None) -> None:
        self.cfg = SymbolGraphConfig.model_validate(config or {})

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        symbol_patterns = [
            r"\b[A-Z_]{2,}\b",
            r"\b[A-Z][a-z]+(?:Error|Exception|Factory|Builder|Manager|Service|Provider)\b",
            r"\b[A-Z][a-z]+(?:API|SDK|DTO|VO|DAO|REST|SOAP|CLI|GUI)\b",
        ]
        for ctx in contexts:
            symbols = set()

            for pat in symbol_patterns:
                symbols.update(re.findall(pat, ctx.content))

                symbol_density = len(symbols) / max(1, len(set(ctx.content.split())))

                score = symbol_density * self.cfg.symbol_weight

                ctx.relevance_score = round(min(1.0, ctx.relevance_score + score), 4)

        return contexts
