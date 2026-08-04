"""Document chunking for the RAG pipeline.

Splits text into chunks using a recursive strategy:
markdown headings → paragraphs → sentences → character window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class ChunkingConfig(BaseModel):
    chunk_size: int = 500
    chunk_overlap: int = 50
    min_chunk_size: int = 50
    respect_headings: bool = True
    respect_paragraphs: bool = True


_SEPARATORS: list[str] = [
    r"\n#{1,6}\s+",  # Markdown headings (##, ###, etc.)
    r"\n\n",         # Paragraph breaks
    r"\n",           # Line breaks
    r"\.\s+",        # Sentences
    r",\s+",         # Clauses
    r"\s+",          # Words / character-level fallback
]


def _split_with_pattern(text: str, pattern: str) -> list[str]:
    parts = re.split(f"({pattern})", text, maxsplit=0)
    result: list[str] = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and re.match(pattern, parts[i + 1]):
            result.append(parts[i] + parts[i + 1])
            i += 2
        else:
            if parts[i]:
                result.append(parts[i])
            i += 1
    return result


@dataclass
class RecursiveCharacterChunker:
    """Recursively splits text by decreasing separator priority.

    Tries markdown headings first, then paragraphs, then sentences,
    then character windows — always respecting ``chunk_size``.
    """

    chunk_size: int = 500
    chunk_overlap: int = 50
    min_chunk_size: int = 50

    def chunk(self, text: str) -> list[str]:
        if not text.strip():
            return []
        return self._chunk_recursive([text], 0)

    def _chunk_recursive(self, texts: list[str], sep_idx: int) -> list[str]:
        if sep_idx >= len(_SEPARATORS):
            return self._split_by_size(texts)

        result: list[str] = []
        for t in texts:
            if len(t) <= self.chunk_size:
                result.append(t)
                continue
            parts = _split_with_pattern(t, _SEPARATORS[sep_idx])
            if len(parts) == 1:
                result.extend(self._chunk_recursive([t], sep_idx + 1))
            else:
                merged = self._merge_small(parts)
                result.extend(self._chunk_recursive(merged, sep_idx + 1))
        return self._merge_small(result)

    def _split_by_size(self, texts: list[str]) -> list[str]:
        result: list[str] = []
        for t in texts:
            if len(t) <= self.chunk_size:
                result.append(t)
            else:
                result.extend(self._window_split(t))
        return result

    def _window_split(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            if end < len(text):
                break_at = text.rfind(" ", start, end + 1)
                if break_at > start:
                    end = break_at
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end + (0 if end >= len(text) else 1)
            if start < len(text):
                start = max(start - self.chunk_overlap, start)
        return chunks

    def _merge_small(self, texts: list[str]) -> list[str]:
        if not texts:
            return texts
        result: list[str] = []
        buf = ""
        for t in texts:
            if not buf:
                buf = t
            elif len(buf) + len(t) < self.chunk_size:
                buf += "\n\n" + t
            else:
                if buf.strip():
                    result.append(buf)
                buf = t
        if buf.strip():
            result.append(buf)
        return result


def chunk_document(text: str, **kwargs: Any) -> list[str]:
    """Split *text* into chunks using default or provided config.

    Args:
        text: Input document text.
        **kwargs: Override any ``ChunkingConfig`` field (chunk_size,
                  chunk_overlap, min_chunk_size, respect_headings,
                  respect_paragraphs).

    Returns:
        List of text chunks.
    """
    config = ChunkingConfig(**kwargs)
    chunker = RecursiveCharacterChunker(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        min_chunk_size=config.min_chunk_size,
    )
    return chunker.chunk(text)
