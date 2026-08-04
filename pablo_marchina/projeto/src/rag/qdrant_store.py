"""Qdrant-backed vector store — persistent, filterable, optional.

Epic 15: Adds ``QdrantStore(VectorStore)`` as a production-ready backend
while preserving the in-memory fallback for development and testing.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.rag.vector_store import VectorEntry, VectorStore

if TYPE_CHECKING:
    from qdrant_client import QdrantClient


_PAYLOAD_INDEX_FIELDS = [
    "product",
    "gap_types",
    "source_id",
    "version",
    "document_type",
    "content_hash",
    "is_active",
    "corpus_version",
    "nvidia_technology",
]

_POINT_ID_PREFIX = "nvidia-startup-ai-radar:nvidia_corpus:"


class QdrantConnectionError(Exception):
    """Raised when Qdrant is unreachable or returns an unexpected error."""


@dataclass
class QdrantConfig:
    """Configuration for connecting to a Qdrant instance.

    Defaults are read from environment so ingestion, runtime, and product
    readiness checks use one source of truth.
    """

    url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key: str | None = os.getenv("QDRANT_API_KEY") or None
    collection_name: str = os.getenv("QDRANT_COLLECTION", "nvidia_corpus")
    vector_size: int = int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))
    timeout: int = int(os.getenv("QDRANT_TIMEOUT_SECONDS", "10"))


# ------------------------------------------------------------------
# QdrantStore
# ------------------------------------------------------------------


class QdrantStore(VectorStore):
    """Vector store backed by a Qdrant collection.

    Every entry is upserted as a Qdrant point with a rich payload
    that preserves provenance and supports server-side filtering.

    Parameters
    ----------
    config:
        Connection and collection settings.
    """

    def __init__(self, config: QdrantConfig | None = None) -> None:
        self._config = config or QdrantConfig()
        self._client: QdrantClient | None = None  # lazy — set on first access
        self._models: Any = None

    # ------------------------------------------------------------------
    # Lazy connection
    # ------------------------------------------------------------------

    def _ensure_client(self) -> None:
        """Connect to Qdrant on first use."""
        if self._client is not None:
            return
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qdrant_models

            self._models = qdrant_models
            self._client = QdrantClient(
                url=self._config.url,
                api_key=self._config.api_key or None,
                timeout=self._config.timeout,
            )
            self._ensure_collection()
        except ImportError as err:
            raise QdrantConnectionError(
                "qdrant-client is not installed.  Install it with: pip install qdrant-client"
            ) from err
        except Exception as exc:
            raise QdrantConnectionError(f"Cannot connect to Qdrant at {self._config.url}: {exc}") from exc

    def _ensure_collection(self) -> None:
        """Create the collection if it does not exist."""
        assert self._client is not None
        assert self._models is not None
        collections = self._client.get_collections().collections  # type: ignore[attr-defined]
        existing = {c.name for c in collections}
        if self._config.collection_name not in existing:
            self._client.create_collection(  # type: ignore[attr-defined]
                collection_name=self._config.collection_name,
                vectors_config=self._models.VectorParams(
                    size=self._config.vector_size,
                    distance=self._models.Distance.COSINE,
                ),
            )
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self) -> None:
        """Create payload indexes if they do not exist."""
        assert self._client is not None
        assert self._models is not None
        try:
            existing = set(
                self._client.get_collection(  # type: ignore[attr-defined]
                    self._config.collection_name
                ).payload_schema.keys()
            )
        except Exception:
            existing = set()
        for field in _PAYLOAD_INDEX_FIELDS:
            if field not in existing:
                field_type = (
                    self._models.PayloadSchemaType.BOOL
                    if field == "is_active"
                    else (self._models.PayloadSchemaType.KEYWORD)
                )
                try:
                    self._client.create_payload_index(  # type: ignore[attr-defined]
                        collection_name=self._config.collection_name,
                        field_name=field,
                        field_type=field_type,
                        wait=True,
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_entry(self, entry: VectorEntry) -> None:
        """Upsert a single entry as a Qdrant point."""
        self._ensure_client()
        assert self._client is not None
        point = _entry_to_point(entry, self._models)
        self._client.upsert(  # type: ignore[attr-defined]
            collection_name=self._config.collection_name,
            points=[point],
        )

    def add_entries(self, entries: list[VectorEntry]) -> None:
        """Upsert multiple entries in a single batch."""
        self._ensure_client()
        assert self._client is not None
        points = [_entry_to_point(e, self._models) for e in entries]
        self._client.upsert(  # type: ignore[attr-defined]
            collection_name=self._config.collection_name,
            points=points,
        )

    def remove_entry(self, chunk_id: str) -> None:
        """Delete a single point by chunk_id."""
        self._ensure_client()
        assert self._client is not None
        assert self._models is not None
        self._client.delete(  # type: ignore[attr-defined]
            collection_name=self._config.collection_name,
            points_selector=self._models.FilterSelector(
                filter=self._models.Filter(
                    must=[
                        self._models.FieldCondition(
                            key="chunk_id",
                            match=self._models.MatchValue(value=chunk_id),
                        )
                    ]
                )
            ),
        )

    def clear(self) -> None:
        """Delete and recreate the collection."""
        self._ensure_client()
        assert self._client is not None
        assert self._models is not None
        self._client.recreate_collection(  # type: ignore[attr-defined]
            collection_name=self._config.collection_name,
            vectors_config=self._models.VectorParams(
                size=self._config.vector_size,
                distance=self._models.Distance.COSINE,
            ),
        )
        self._ensure_payload_indexes()

    def get_entry(self, chunk_id: str) -> VectorEntry | None:
        """Retrieve a single point by chunk_id."""
        self._ensure_client()
        assert self._client is not None
        points = self._client.scroll(  # type: ignore[attr-defined]
            collection_name=self._config.collection_name,
            limit=1,
            scroll_filter=self._models.Filter(
                must=[
                    self._models.FieldCondition(
                        key="chunk_id",
                        match=self._models.MatchValue(value=chunk_id),
                    )
                ]
            ),
        )[0]
        if not points:
            return None
        return _point_to_entry(points[0])

    @property
    def size(self) -> int:
        self._ensure_client()
        assert self._client is not None
        return self._client.count(  # type: ignore[no-any-return, attr-defined]
            collection_name=self._config.collection_name
        ).count

    @property
    def entries(self) -> list[VectorEntry]:
        self._ensure_client()
        assert self._client is not None
        points, _ = self._client.scroll(  # type: ignore[attr-defined]
            collection_name=self._config.collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=True,
        )
        return [_point_to_entry(p) for p in points]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

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
        """Search with server-side metadata filters."""
        self._ensure_client()
        assert self._client is not None
        assert self._models is not None
        must_conditions: list[Any] = []

        if product:
            must_conditions.append(
                self._models.FieldCondition(
                    key="product",
                    match=self._models.MatchValue(value=product.lower()),
                )
            )
        if gap_type:
            must_conditions.append(
                self._models.FieldCondition(
                    key="gap_types",
                    match=self._models.MatchValue(value=gap_type),
                )
            )
        if source_id:
            must_conditions.append(
                self._models.FieldCondition(
                    key="source_id",
                    match=self._models.MatchValue(value=source_id),
                )
            )
        if version:
            must_conditions.append(
                self._models.FieldCondition(
                    key="version",
                    match=self._models.MatchValue(value=version),
                )
            )
        if document_type:
            must_conditions.append(
                self._models.FieldCondition(
                    key="document_type",
                    match=self._models.MatchValue(value=document_type),
                )
            )
        if not include_deprecated:
            must_conditions.append(
                self._models.FieldCondition(
                    key="is_active",
                    match=self._models.MatchValue(value=True),
                )
            )

        query_filter = self._models.Filter(must=must_conditions) if must_conditions else None

        results = self._client.query_points(  # type: ignore[attr-defined]
            collection_name=self._config.collection_name,
            query=query_embedding,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=True,
        )

        entries = [_point_to_entry(p) for p in results.points]
        if not include_deprecated:
            entries = [e for e in entries if e.is_active is True and not e.deprecated_at and not e.superseded_by]
        if not include_expired:
            entries = [e for e in entries if not _is_expired(e.valid_until)]
        return entries


# ------------------------------------------------------------------
# Payload helpers
# ------------------------------------------------------------------


def _entry_to_point(entry: VectorEntry, models_module: Any) -> Any:
    """Convert a ``VectorEntry`` to a Qdrant ``PointStruct``."""
    now = datetime.now(UTC).isoformat()
    chunk_hash = entry.chunk_hash or hashlib.md5(entry.content.encode("utf-8"), usedforsecurity=False).hexdigest()

    return models_module.PointStruct(
        id=_point_id_for_chunk(entry.chunk_id),
        vector=entry.embedding,
        payload={
            "chunk_id": entry.chunk_id,
            "source_id": entry.source_id,
            "source_title": entry.title,
            "source_url": entry.url or "",
            "product": entry.product,
            "nvidia_technology": entry.nvidia_technology or entry.product,
            "gap_types": list(entry.gap_types),
            "version": entry.version,
            "corpus_version": entry.corpus_version,
            "chunk_text": entry.content,
            "content": entry.content,
            "chunk_index": entry.chunk_index,
            "char_count": entry.char_count or len(entry.content),
            "ingested_at": entry.ingested_at or now,
            "content_hash": entry.content_hash or chunk_hash,
            "previous_content_hash": entry.previous_content_hash or "",
            "chunk_hash": chunk_hash,
            "collected_at": entry.collected_at or now,
            "last_checked_at": entry.last_checked_at or "",
            "valid_from": entry.valid_from or "",
            "valid_until": entry.valid_until or "",
            "freshness_policy": entry.freshness_policy or "",
            "stale_after_days": entry.stale_after_days,
            "is_active": entry.is_active,
            "deprecated_at": entry.deprecated_at or "",
            "superseded_by": entry.superseded_by or "",
            "deprecation_reason": entry.deprecation_reason or "",
            "document_type": entry.document_type,
            "provenance": {
                "source_url": entry.url or "",
                "source_title": entry.title,
            },
            "ingestion_run_id": entry.ingestion_run_id or "",
        },
    )


def _point_id_for_chunk(chunk_id: str) -> str:
    """Return a deterministic Qdrant-compatible point id for a chunk."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{_POINT_ID_PREFIX}{chunk_id}"))


def _point_to_entry(point: Any) -> VectorEntry:
    """Convert a Qdrant ``ScoredPoint`` back to a ``VectorEntry``."""
    payload = point.payload or {}
    vector = list(point.vector or [])

    return VectorEntry(
        chunk_id=payload.get("chunk_id", point.id),
        source_id=payload.get("source_id", ""),
        title=payload.get("source_title", ""),
        content=payload.get("chunk_text") or payload.get("content", ""),
        product=payload.get("product", ""),
        gap_types=list(payload.get("gap_types", [])),
        url=payload.get("source_url") or None,
        embedding=vector,
        version=payload.get("version", "1.0"),
        document_type=payload.get("document_type", "nvidia_corpus"),
        content_hash=payload.get("content_hash"),
        chunk_hash=payload.get("chunk_hash"),
        ingestion_run_id=payload.get("ingestion_run_id"),
        previous_content_hash=payload.get("previous_content_hash") or None,
        collected_at=payload.get("collected_at") or None,
        last_checked_at=payload.get("last_checked_at") or None,
        valid_from=payload.get("valid_from") or None,
        valid_until=payload.get("valid_until") or None,
        freshness_policy=payload.get("freshness_policy") or None,
        stale_after_days=payload.get("stale_after_days"),
        is_active=payload.get("is_active", True),
        deprecated_at=payload.get("deprecated_at") or None,
        superseded_by=payload.get("superseded_by") or None,
        deprecation_reason=payload.get("deprecation_reason") or None,
        nvidia_technology=payload.get("nvidia_technology", ""),
        corpus_version=payload.get("corpus_version", "1.0"),
        chunk_index=payload.get("chunk_index", 0),
        char_count=payload.get("char_count", 0),
        ingested_at=payload.get("ingested_at", ""),
    )


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


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def build_qdrant_store(
    url: str | None = None,
    collection_name: str | None = None,
    vector_size: int | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
) -> QdrantStore:
    """Build a ``QdrantStore`` from explicit parameters (falls back to env).

    Parameters are optional — if not provided the factory reads from
    environment variables (via ``QdrantConfig`` defaults).
    """
    config = QdrantConfig(
        url=url or os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=api_key if api_key is not None else (os.getenv("QDRANT_API_KEY") or None),
        collection_name=collection_name or os.getenv("QDRANT_COLLECTION", "nvidia_corpus"),
        vector_size=vector_size or int(os.getenv("QDRANT_VECTOR_SIZE", "1024")),
        timeout=timeout or int(os.getenv("QDRANT_TIMEOUT_SECONDS", "10")),
    )
    return QdrantStore(config=config)
