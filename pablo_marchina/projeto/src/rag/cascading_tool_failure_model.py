from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_CASCADE_PATTERNS = [
    re.compile(r"failed\s+because|error\s+propagat", re.IGNORECASE),
    re.compile(r"(timeout|error)\s+in\s+(tool|function|API)\s+\w+\s+(caused|led|triggered)", re.IGNORECASE),
    re.compile(r"cascading\s+(failure|error)", re.IGNORECASE),
    re.compile(r"dependent\s+(tool|service|API)\s+(failed|unavailable|down)", re.IGNORECASE),
    re.compile(r"chain\s+of\s+failures", re.IGNORECASE),
    re.compile(r"(nested|chained)\s+(error|exception|failure)", re.IGNORECASE),
    re.compile(r"(subsequent|downstream)\s+(call|request)\s+failed", re.IGNORECASE),
    re.compile(r"unhandled\s+(error|exception)", re.IGNORECASE),
]


class CascadingToolFailureModel:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        risk_scores = []
        for ctx in contexts:
            severity = self._compute_severity(ctx)

            risk_scores.append(severity)

            if severity > 0:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - severity), 4)

        return contexts

    def _compute_severity(self, ctx: RetrievedContext) -> float:
        hits = sum(1 for p in _CASCADE_PATTERNS if p.search(ctx.content))
        if hits >= 3:
            return 0.5
        if hits >= 1:
            return 0.2
        return 0.0
