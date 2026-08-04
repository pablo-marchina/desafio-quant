from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_RISK_LEVEL_PATTERNS = {
    "critical": [
        re.compile(r"(data\s+)?(breach|exfiltrat|leak)", re.IGNORECASE),
        re.compile(r"system\s+compromis", re.IGNORECASE),
        re.compile(r"remote\s+code\s+execution", re.IGNORECASE),
        re.compile(r"privilege\s+escalation", re.IGNORECASE),
    ],
    "high": [
        re.compile(r"denial\s+of\s+service", re.IGNORECASE),
        re.compile(r"cross[-\s]?site\s+scripting", re.IGNORECASE),
        re.compile(r"sql\s+injection", re.IGNORECASE),
        re.compile(r"path\s+traversal", re.IGNORECASE),
    ],
    "medium": [
        re.compile(r"misconfigur", re.IGNORECASE),
        re.compile(r"information\s+disclosure", re.IGNORECASE),
        re.compile(r"weak\s+(authentication|authorization)", re.IGNORECASE),
    ],
    "low": [
        re.compile(r"(minor|cosmetic)\s+(issue|risk)", re.IGNORECASE),
        re.compile(r"informational", re.IGNORECASE),
    ],
}

_RISK_WEIGHTS = {"critical": 0.6, "high": 0.4, "medium": 0.2, "low": 0.05}


class TrajectoryRiskModel:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            total_penalty = self._assess_risk(ctx.content)

            if total_penalty > 0:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - total_penalty), 4)

        return contexts

    def _assess_risk(self, content: str) -> float:
        total = 0.0
        for level, patterns in _RISK_LEVEL_PATTERNS.items():
            hits = sum(1 for p in patterns if p.search(content))
            if hits:
                total += _RISK_WEIGHTS[level] * min(hits, 3)
        return min(total, 1.0)
