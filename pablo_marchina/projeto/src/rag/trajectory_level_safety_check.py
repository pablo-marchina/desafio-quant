from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_TRAJECTORY_SAFETY_PATTERNS = [
    re.compile(r"(logged|recorded|stored)\s+(user|sensitive|personal)\s+(data|info)", re.IGNORECASE),
    re.compile(r"(exposed|leaked|revealed)\s+(credentials?|token|key|password)", re.IGNORECASE),
    re.compile(r"(unsafe|dangerous|harmful)\s+(action|operation|command)", re.IGNORECASE),
    re.compile(r"bypassed?\s+(safety|security|guardrail)", re.IGNORECASE),
    re.compile(r"escalat(ed|ing)\s+(privileges?|permissions?)", re.IGNORECASE),
    re.compile(r"access\s+denied", re.IGNORECASE),
    re.compile(r"unauthorized\s+access", re.IGNORECASE),
    re.compile(r"data\s+(breach|loss|corruption)", re.IGNORECASE),
]


class TrajectoryLevelSafetyCheck:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            hits = sum(1 for p in _TRAJECTORY_SAFETY_PATTERNS if p.search(ctx.content))

            if hits >= 1:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.3 * hits), 4)

        return contexts
