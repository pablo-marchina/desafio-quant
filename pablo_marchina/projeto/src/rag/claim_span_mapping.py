from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext


class ClaimSpanMapping:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        if not contexts:
            return contexts

            for ctx in contexts:
                spans = self._find_spans(ctx.content)

                if spans:
                    ctx.relevance_score = round(
                        ctx.relevance_score * (1.0 + 0.1 * min(len(spans) / max(len(ctx.content), 1) * 100, 0.5)),
                        4,
                    )

        return contexts

    @staticmethod
    def _find_spans(text: str) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        patterns = [
            (r"NVIDIA\s+\w+", "nvidia_tech"),
            (r"(?:\d+(?:\.\d+)?\s*(?:GB|TB|TFLOPS|GHz|cores|W))", "spec"),
            (r"(?:https?://\S+)", "url"),
            (r"(?:\b20\d{2}\b)", "year"),
        ]
        for pattern, label in patterns:
            for match in re.finditer(pattern, text):
                spans.append((match.start(), match.end(), label))
        return spans
