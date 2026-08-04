"""Vector store abstraction with in-memory implementation.

Defines a ``VectorStore`` ABC that both ``InMemoryVectorStore`` and
``QdrantStore`` implement.  Swap backends via config without changing
retrieval code.
"""

from __future__ import annotations

import math
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class VectorEntry:
    """A chunk stored in the vector store with its embedding."""

    chunk_id: str
    source_id: str
    title: str
    content: str
    product: str
    gap_types: list[str] = field(default_factory=list)
    url: str | None = None
    embedding: list[float] = field(default_factory=list)
    version: str = "1.0"
    document_type: str = "nvidia_corpus"
    content_hash: str | None = None
    chunk_hash: str | None = None
    ingestion_run_id: str | None = None
    previous_content_hash: str | None = None
    collected_at: str | None = None
    last_checked_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    freshness_policy: str | None = None
    stale_after_days: int | None = None
    is_active: bool = True
    deprecated_at: str | None = None
    superseded_by: str | None = None
    deprecation_reason: str | None = None
    nvidia_technology: str = ""
    corpus_version: str = "1.0"
    chunk_index: int = 0
    char_count: int = 0
    ingested_at: str = ""


class VectorStore(ABC):
    """Abstract vector store — supports add, remove, clear, search."""

    @abstractmethod
    def add_entry(self, entry: VectorEntry) -> None:
        """Add or replace a single entry by chunk_id."""

    @abstractmethod
    def add_entries(self, entries: list[VectorEntry]) -> None:
        """Add multiple entries in one call."""

    @abstractmethod
    def remove_entry(self, chunk_id: str) -> None:
        """Remove a single entry by chunk_id."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all entries."""

    @abstractmethod
    def get_entry(self, chunk_id: str) -> VectorEntry | None:
        """Look up a single entry by chunk_id."""

    @property
    @abstractmethod
    def size(self) -> int:
        """Number of entries currently stored."""

    @property
    @abstractmethod
    def entries(self) -> list[VectorEntry]:
        """Return all entries."""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        *,
        product: str | None = None,
        gap_type: str | None = None,
        source_id: str | None = None,
        version: str | None = None,
        document_type: str | None = None,
        include_deprecated: bool = False,
        include_expired: bool = False,
    ) -> list[VectorEntry]:
        """Cosine-similarity search with optional metadata filters.

        Parameters
        ----------
        query_embedding:
            The embedding vector to search for.
        top_k:
            Maximum number of results to return.
        product:
            If set, only return entries whose ``product`` matches (case-insensitive).
        gap_type:
            If set, only return entries whose ``gap_types`` contains this value.
        source_id:
            If set, only return entries whose ``source_id`` matches.
        version:
            If set, only return entries whose ``version`` matches.
        document_type:
            If set, only return entries whose ``document_type`` matches.
        include_deprecated:
            If false, return only active entries without deprecation metadata.
        include_expired:
            If false, exclude entries whose ``valid_until`` is in the past.

        Returns
        -------
        list[VectorEntry]
            Up to ``top_k`` entries sorted by descending similarity.
        """


class InMemoryVectorStore(VectorStore):
    """Dict-backed vector store with cosine similarity search.

    No external dependencies.  Supports filters by product, gap_type,
    source_id, version, and document_type.
    Designed for development and testing — MUST NOT be used in production.
    """

    def __init__(self) -> None:
        _assert_not_production()
        self._entries: dict[str, VectorEntry] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_entry(self, entry: VectorEntry) -> None:
        """Add or replace a single entry by chunk_id."""
        self._entries[entry.chunk_id] = entry

    def add_entries(self, entries: list[VectorEntry]) -> None:
        """Add multiple entries in one call."""
        for e in entries:
            self.add_entry(e)

    def remove_entry(self, chunk_id: str) -> None:
        """Remove a single entry by chunk_id."""
        self._entries.pop(chunk_id, None)

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_entry(self, chunk_id: str) -> VectorEntry | None:
        """Look up a single entry by chunk_id."""
        return self._entries.get(chunk_id)

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list[VectorEntry]:
        return list(self._entries.values())

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        *,
        product: str | None = None,
        gap_type: str | None = None,
        source_id: str | None = None,
        version: str | None = None,
        document_type: str | None = None,
        include_deprecated: bool = False,
        include_expired: bool = False,
    ) -> list[VectorEntry]:
        """Cosine-similarity search with optional metadata filters."""
        candidates = self._filter(
            product=product,
            gap_type=gap_type,
            source_id=source_id,
            version=version,
            document_type=document_type,
            include_deprecated=include_deprecated,
            include_expired=include_expired,
        )
        if not candidates:
            return []

        scored: list[tuple[VectorEntry, float]] = []
        for entry in candidates:
            sim = _cosine_similarity(query_embedding, entry.embedding)
            scored.append((entry, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored[:top_k]]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _filter(
        self,
        product: str | None = None,
        gap_type: str | None = None,
        source_id: str | None = None,
        version: str | None = None,
        document_type: str | None = None,
        include_deprecated: bool = False,
        include_expired: bool = False,
    ) -> list[VectorEntry]:
        """Return all entries matching the given filters."""
        result = self.entries
        if product:
            p_lower = product.lower()
            result = [e for e in result if e.product.lower() == p_lower]
        if gap_type:
            result = [e for e in result if gap_type in e.gap_types]
        if source_id:
            result = [e for e in result if e.source_id == source_id]
        if version:
            result = [e for e in result if e.version == version]
        if document_type:
            result = [e for e in result if e.document_type == document_type]
        if not include_deprecated:
            result = [e for e in result if e.is_active is True and not e.deprecated_at and not e.superseded_by]
        if not include_expired:
            result = [e for e in result if not _is_expired(e.valid_until)]
        return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _assert_not_production() -> None:
    """Raise RuntimeError if APP_MODE=product and RAG_VECTOR_BACKEND=in_memory."""
    app_mode = os.environ.get("APP_MODE", "").lower()
    backend = os.environ.get("RAG_VECTOR_BACKEND", "in_memory").lower()
    if app_mode == "product" and backend == "in_memory":
        raise RuntimeError(
            "InMemoryVectorStore is FORBIDDEN in production. Set RAG_VECTOR_BACKEND=qdrant in your .env file."
        )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns a value in [-1, 1].  Returns 0.0 for zero vectors.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _is_expired(valid_until: str | None) -> bool:
    if not valid_until:
        return False
    try:
        parsed = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC) < datetime.now(UTC)
