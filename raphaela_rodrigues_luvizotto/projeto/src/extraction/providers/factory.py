from __future__ import annotations

from .base import StructuredExtractionProvider
from .groq import GroqStructuredExtractionProvider
from ..config import EXTRACTION_PROVIDER


def build_extraction_provider() -> StructuredExtractionProvider | None:
    try:
        if EXTRACTION_PROVIDER == "groq":
            return GroqStructuredExtractionProvider()
        if EXTRACTION_PROVIDER == "openrouter":
            return None
    except Exception:
        return None
    return None
