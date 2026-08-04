from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_AUTONOMY_RISK_PATTERNS = [
    re.compile(r"(act|decide|proceed)\s+(without|independently|autonomously)", re.IGNORECASE),
    re.compile(r"no\s+(human|manual|user)\s+(review|approval|oversight)", re.IGNORECASE),
    re.compile(r"(unlimited|unbounded|infinite)\s+(access|control|autonomy)", re.IGNORECASE),
    re.compile(r"(can|may)\s+(execute|run|perform)\s+any", re.IGNORECASE),
    re.compile(r"no\s+(restrictions?|limits?|boundaries?)", re.IGNORECASE),
    re.compile(r"self[-\s]?governing", re.IGNORECASE),
    re.compile(r"autonomous\s+(agent|system|decision)", re.IGNORECASE),
    re.compile(r"unconstrained\s+(execution|operation)", re.IGNORECASE),
    re.compile(r"full\s+(control|authority|autonomy)", re.IGNORECASE),
]


class UnboundedAutonomyRisk:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("autonomy_threshold", 2))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _AUTONOMY_RISK_PATTERNS if p.search(ctx.content))

            if hits >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.3), 4)

        return contexts
