from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class EvidenceExtractionBeforeGeneration:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                evidence_spans = self._extract_evidence(ctx.content)

                if evidence_spans:
                    evidence_ratio = len(" ".join(evidence_spans)) / max(len(ctx.content), 1)

                    ctx.relevance_score = round(ctx.relevance_score * (0.5 + 0.5 * evidence_ratio), 4)

        return contexts

    @staticmethod
    def _extract_evidence(text: str) -> list[str]:
        spans: list[str] = []
        patterns = [
            (r'"([^"]+)"', 1),
            (r"'([^']+)'", 1),
            (r"\(([^)]+)\)", 1),
            (r"(?:according to|based on|per|source:)\s+([^\.]+)", 0),
        ]
        for pattern, group in patterns:
            for match in re.finditer(pattern, text):
                span = match.group(group).strip()
                if len(span) > 15:
                    spans.append(span)
        return spans[:5]
