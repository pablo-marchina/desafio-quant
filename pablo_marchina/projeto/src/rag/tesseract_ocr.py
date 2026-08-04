from __future__ import annotations

import re
from typing import Any

from src.rag.schemas import RetrievedContext

_OCR_NOISE = re.compile(r'[^\w\s{}[\]()|:;\'",.<>!?@#$%^&*+\-=/\\~`]')
_LONG_WORDS = re.compile(r"\b\w{20,}\b")
_REPEATED_CHARS = re.compile(r"(.)\1{4,}")


class TesseractOcr:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config or {}

    @staticmethod
    def _ocr_quality(text: str) -> float:
        if not text.strip():
            return 0.0
        noise_chars = len(_OCR_NOISE.findall(text))
        long_words = len(_LONG_WORDS.findall(text))
        repeats = len(_REPEATED_CHARS.findall(text))
        score = 1.0 - (noise_chars / max(len(text), 1)) - (long_words * 0.05) - (repeats * 0.1)
        return round(max(0.0, min(1.0, score)), 4)

    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        for ctx in contexts:
            quality = self._ocr_quality(ctx.content)
            ctx.content = f"[ocr_quality:{quality}]\n{ctx.content}"
        return contexts
