"""Fuzzy deduplication for collected text content.

Uses ``rapidfuzz`` for fast token-set ratio comparisons.  Two documents
are considered duplicates when their similarity ratio exceeds the configured
threshold (default 0.85).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from hashlib import sha256
from threading import Lock

from rapidfuzz import fuzz

from src.scraping.config import config as _cfg

logger = logging.getLogger(__name__)


@dataclass
class FuzzyIndex:
    """Incremental index that tracks seen text fingerprints."""

    threshold: float = 0.85
    _seen: list[str] = field(default_factory=list)

    def is_duplicate(self, text: str) -> bool:
        """Return ``True`` if *text* is a near-duplicate of any indexed text."""
        if not text.strip():
            return False
        for existing in self._seen:
            ratio = fuzz.token_set_ratio(text, existing) / 100.0
            if ratio >= self.threshold:
                logger.debug("DEDUP  ratio=%.2f  threshold=%.2f", ratio, self.threshold)
                return True
        return False

    def index(self, text: str) -> None:
        """Add *text* to the index for future comparisons."""
        self._seen.append(text)

    def clear(self) -> None:
        self._seen.clear()


def content_hash(text: str) -> str:
    """Return a SHA-256 hex digest of the trimmed, lowercased text."""
    return sha256(text.strip().lower().encode()).hexdigest()


def exact_dedup(existing_hashes: set[str], text: str) -> bool:
    """Exact (SHA-256) dedup check — O(1), no false positives."""
    h = content_hash(text)
    if h in existing_hashes:
        return True
    existing_hashes.add(h)
    return False


@dataclass
class DedupIndex:
    """Unified dedup index combining exact (SHA-256) and fuzzy (token_set_ratio) checks.

    Usage::

        idx = DedupIndex(threshold=0.85)
        if idx.is_duplicate(text):
            ...  # skip
        else:
            idx.index(text)  # store for future checks
    """

    threshold: float = _cfg.fuzzy_dedup.threshold
    _hashes: set[str] = field(default_factory=set)
    _texts: list[str] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def is_duplicate(self, text: str) -> bool:
        """Return ``True`` if *text* is a duplicate (exact or fuzzy)."""
        stripped = text.strip()
        if not stripped:
            return False

        with self._lock:
            h = content_hash(stripped)
            if h in self._hashes:
                return True
            for existing in self._texts:
                ratio = fuzz.token_set_ratio(stripped, existing) / 100.0
                if ratio >= self.threshold:
                    logger.debug("DEDUP  ratio=%.2f  threshold=%.2f", ratio, self.threshold)
                    return True
        return False

    def index(self, text: str) -> None:
        """Store *text* for future duplicate checks."""
        stripped = text.strip()
        if not stripped:
            return
        with self._lock:
            h = content_hash(stripped)
            self._hashes.add(h)
            self._texts.append(stripped)

    def clear(self) -> None:
        """Reset the index."""
        with self._lock:
            self._hashes.clear()
            self._texts.clear()
