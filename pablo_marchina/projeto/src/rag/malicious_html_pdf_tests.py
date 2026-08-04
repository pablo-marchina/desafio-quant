from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_HTML_MALICIOUS_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"onerror\s*=", re.IGNORECASE),
    re.compile(r"onload\s*=", re.IGNORECASE),
    re.compile(r"onclick\s*=", re.IGNORECASE),
    re.compile(r"onmouseover\s*=", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"<embed[^>]*>", re.IGNORECASE),
    re.compile(r"<object[^>]*>", re.IGNORECASE),
    re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"<meta[^>]*http-equiv\s*=\s*\"refresh\"", re.IGNORECASE),
    re.compile(r"eval\s*\(.*?\)", re.IGNORECASE),
    re.compile(r"execCommand", re.IGNORECASE),
]

_PDF_MALICIOUS_PATTERNS = [
    re.compile(r"/JavaScript", re.IGNORECASE),
    re.compile(r"/Launch\b", re.IGNORECASE),
    re.compile(r"/EmbeddedFile", re.IGNORECASE),
    re.compile(r"/OpenAction", re.IGNORECASE),
    re.compile(r"/AA\s*<<", re.IGNORECASE),
]


class MaliciousHtmlPdfTests:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}
        self._threshold = int(self.config.get("malicious_threshold", 1))

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        return self._apply(contexts, **kwargs)

    def _apply(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            html_hits = sum(1 for p in _HTML_MALICIOUS_PATTERNS if p.search(ctx.content))

            pdf_hits = sum(1 for p in _PDF_MALICIOUS_PATTERNS if p.search(ctx.content))

            total = html_hits + pdf_hits

            if total >= self._threshold:
                ctx.relevance_score = round(max(0.0, ctx.relevance_score - 0.5 * total), 4)

        return contexts
