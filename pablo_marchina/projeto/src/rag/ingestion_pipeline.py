"""Corpus ingestion pipeline: load, chunk, embed, upsert, validate, readiness.

Usage (programmatic)::

    from src.rag.ingestion_pipeline import run_ingestion_pipeline, check_corpus_readiness

    report = run_ingestion_pipeline(embedding_provider, vector_store)
    readiness = check_corpus_readiness(vector_store)
    if not readiness.production_allowed:
        raise SystemExit(readiness.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    get_project_decision_inventory,
    validate_decision_for_production,
)
from src.rag.embeddings import EmbeddingProvider
from src.rag.ingestion import load_and_chunk_corpus
from src.rag.qdrant_store import QdrantConnectionError
from src.rag.schemas import RagChunk
from src.rag.vector_store import VectorEntry, VectorStore

CORPUS_VERSION = "1.0"

REQUIRED_PAYLOAD_FIELDS: list[str] = [
    "chunk_id",
    "source_id",
    "source_title",
    "source_url",
    "nvidia_technology",
    "corpus_version",
    "chunk_text",
    "chunk_index",
    "char_count",
    "ingested_at",
]

REQUIRED_INGESTION_DECISIONS: list[str] = [
    "rag.chunk_size",
    "rag.chunk_overlap",
    "rag.ingestion_batch_size",
    "rag.min_corpus_documents",
    "rag.min_corpus_chunks",
    "rag.corpus_staleness_policy",
    "rag.embedding_dimension_expected",
]

# ---------------------------------------------------------------------------
# Ingestion report
# ---------------------------------------------------------------------------


@dataclass
class IngestionReport:
    corpus_version: str = CORPUS_VERSION
    document_count: int = 0
    chunk_count: int = 0
    embedded_chunk_count: int = 0
    upserted_point_count: int = 0
    skipped_chunk_count: int = 0
    failed_chunk_count: int = 0
    embedding_dimension: int = 0
    collection_name: str = ""
    payload_schema_valid_count: int = 0
    payload_schema_invalid_count: int = 0
    ingestion_status: str = "pending"
    blockers: list[str] = field(default_factory=list)
    ingestion_run_id: str = ""
    started_at: str = ""
    finished_at: str = ""


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------


def validate_payload_schema(point: dict[str, Any]) -> list[str]:
    """Check that a Qdrant point payload contains all required fields."""
    missing: list[str] = []
    for field_name in REQUIRED_PAYLOAD_FIELDS:
        val = point.get(field_name)
        if val is None or (isinstance(val, str) and val == ""):
            missing.append(field_name)
    return missing


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    return None


# ---------------------------------------------------------------------------
# Calibration validation for ingestion decisions
# ---------------------------------------------------------------------------


def _check_ingestion_calibrations() -> tuple[dict[str, Any], list[str]]:
    """Validate all required ingestion decisions are calibrated.

    Returns (calibrated_values, blockers).
    """
    inventory = get_project_decision_inventory()
    values: dict[str, Any] = {}
    blockers: list[str] = []

    for decision_id in REQUIRED_INGESTION_DECISIONS:
        found = False
        for rec in inventory:
            if rec.decision_id == decision_id:
                found = True
                validation = validate_decision_for_production(rec)
                if not validation.passed:
                    blockers.append(f"Ingestion decision '{decision_id}' blocked: {'; '.join(validation.reasons)}")
                elif rec.calibration_status in (
                    CalibrationStatus.UNCALIBRATED,
                    CalibrationStatus.BLOCKED,
                ):
                    blockers.append(
                        f"Ingestion decision '{decision_id}' is {rec.calibration_status.value} "
                        f"(production_allowed={rec.production_allowed})"
                    )
                else:
                    values[decision_id] = rec.current_value
                break
        if not found:
            blockers.append(f"Ingestion decision '{decision_id}' not found in registry")

    return values, blockers


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------


def run_ingestion_pipeline(
    embedding_provider: EmbeddingProvider,
    vector_store: VectorStore,
    *,
    batch_size: int = 32,
    corpus_version: str = CORPUS_VERSION,
    allow_uncalibrated: bool = False,
) -> IngestionReport:
    """Run the full ingestion pipeline: load, chunk, embed, upsert, validate.

    Parameters
    ----------
    embedding_provider:
        Provider used to embed chunk texts.
    vector_store:
        Target vector store (QdrantStore or InMemoryVectorStore).
    batch_size:
        Number of chunks per upsert batch.
    corpus_version:
        Version tag stamped on every ingested point.
    allow_uncalibrated:
        If True, skip calibration check (for testing only).

    Returns
    -------
    IngestionReport
        Detailed report with counts, status, and blockers.
    """
    run_id = f"ingestion_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    started_at = datetime.now(UTC).isoformat()

    report = IngestionReport(
        corpus_version=corpus_version,
        ingestion_run_id=run_id,
        started_at=started_at,
        collection_name=getattr(getattr(vector_store, "_config", None), "collection_name", ""),
    )

    blockers: list[str] = []

    # 1. Check calibration decisions (unless explicitly bypassed for testing)
    if not allow_uncalibrated:
        cal_values, cal_blockers = _check_ingestion_calibrations()
        if cal_blockers:
            report.ingestion_status = "blocked_uncalibrated_ingestion"
            report.blockers = cal_blockers
            report.finished_at = datetime.now(UTC).isoformat()
            return report

    # 2. Load and chunk corpus
    all_chunks: list[RagChunk] = load_and_chunk_corpus()
    report.chunk_count = len(all_chunks)

    source_ids = {c.source_id for c in all_chunks}
    report.document_count = len(source_ids)

    if not all_chunks:
        report.ingestion_status = "blocked_empty_corpus"
        report.blockers = ["Corpus is empty — no chunks to ingest"]
        report.finished_at = datetime.now(UTC).isoformat()
        return report

    # 3. Generate embeddings
    texts = [c.content for c in all_chunks]
    try:
        embeddings = embedding_provider.embed_batch(texts)
    except Exception as exc:
        report.ingestion_status = "failed_embedding"
        report.blockers = [f"Embedding failed: {exc}"]
        report.finished_at = datetime.now(UTC).isoformat()
        return report

    report.embedded_chunk_count = len(embeddings)
    if embeddings:
        report.embedding_dimension = len(embeddings[0])

    # 4. Build vector entries with payload
    entries: list[VectorEntry] = []
    now_iso = datetime.now(UTC).isoformat()
    skipped = 0

    for chunk, emb in zip(all_chunks, embeddings, strict=True):
        try:
            entry = VectorEntry(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                title=chunk.title,
                content=chunk.content,
                product=chunk.product,
                gap_types=list(chunk.gap_types),
                url=chunk.url,
                embedding=emb,
                version=chunk.version,
                document_type=chunk.document_type,
                content_hash=chunk.content_hash,
                ingestion_run_id=run_id,
                nvidia_technology=chunk.nvidia_technology or chunk.product,
                corpus_version=corpus_version,
                chunk_index=chunk.chunk_index,
                char_count=chunk.char_count or len(chunk.content),
                ingested_at=now_iso,
            )
            entries.append(entry)
        except Exception:
            skipped += 1

    report.skipped_chunk_count = skipped

    # 5. Upsert to vector store
    try:
        total = len(entries)
        for i in range(0, total, batch_size):
            batch = entries[i : i + batch_size]
            vector_store.add_entries(batch)
        report.upserted_point_count = total
    except QdrantConnectionError as exc:
        report.ingestion_status = "blocked_qdrant_unavailable"
        report.blockers = [f"Qdrant unavailable during upsert: {exc}"]
        report.finished_at = datetime.now(UTC).isoformat()
        return report
    except Exception as exc:
        report.ingestion_status = "failed_upsert"
        report.blockers = [f"Upsert failed: {exc}"]
        report.finished_at = datetime.now(UTC).isoformat()
        return report

    # 6. Validate payload schema on stored entries
    stored = vector_store.entries
    for stored_entry in stored:
        payload = {
            "chunk_id": stored_entry.chunk_id,
            "source_id": stored_entry.source_id,
            "source_title": stored_entry.title,
            "source_url": stored_entry.url or "",
            "nvidia_technology": stored_entry.nvidia_technology,
            "corpus_version": stored_entry.corpus_version,
            "chunk_text": stored_entry.content,
            "chunk_index": stored_entry.chunk_index,
            "char_count": stored_entry.char_count,
            "ingested_at": stored_entry.ingested_at,
        }
        missing = validate_payload_schema(payload)
        if missing:
            report.payload_schema_invalid_count += 1
        else:
            report.payload_schema_valid_count += 1

    report.ingestion_status = "completed"
    if report.payload_schema_invalid_count > 0:
        blockers.append(f"{report.payload_schema_invalid_count} point(s) have missing payload fields after upsert")

    report.blockers = blockers
    report.finished_at = datetime.now(UTC).isoformat()
    return report


# ---------------------------------------------------------------------------
# Corpus readiness check
# ---------------------------------------------------------------------------


@dataclass
class CorpusReadinessResult:
    production_allowed: bool
    collection_exists: bool = False
    collection_empty: bool = True
    point_count: int = 0
    embedding_dimension_actual: int = 0
    embedding_dimension_expected: int = 0
    dimension_match: bool = False
    corpus_version_found: str = ""
    corpus_version_valid: bool = False
    payload_schema_valid: bool = False
    min_docs_calibrated: bool = False
    min_chunks_calibrated: bool = False
    min_docs_met: bool = False
    min_chunks_met: bool = False
    actual_document_count: int = 0
    actual_chunk_count: int = 0
    blockers: list[str] = field(default_factory=list)
    calibration_blockers: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"production_allowed={self.production_allowed}",
            f"points={self.point_count}",
            f"docs={self.actual_document_count}",
            f"chunks={self.actual_chunk_count}",
            f"dim={self.embedding_dimension_actual}",
            f"corpus_version={self.corpus_version_found}",
        ]
        if self.blockers:
            parts.append(f"blockers={len(self.blockers)}")
        return " | ".join(parts)


def _count_documents_in_store(vector_store: VectorStore) -> int:
    """Count unique source_ids in vector store."""
    seen: set[str] = set()
    try:
        for entry in vector_store.entries:
            if entry.source_id:
                seen.add(entry.source_id)
    except Exception:
        return 0
    return len(seen)


def check_corpus_readiness(
    vector_store: VectorStore,
    expected_dimension: int = 0,
) -> CorpusReadinessResult:
    """Check if the vector store has a valid, ready corpus.

    Returns a ``CorpusReadinessResult`` with detailed status.
    ``production_allowed`` is ``False`` if any blocker is found.

    Parameters
    ----------
    vector_store:
        The vector store to check (QdrantStore or InMemoryVectorStore).
    expected_dimension:
        Expected embedding dimension. If 0, inferred from first point.
    """
    blockers: list[str] = []
    result = CorpusReadinessResult(production_allowed=False)

    # 1. Check calibration decisions for ingestion
    _, cal_blockers = _check_ingestion_calibrations()
    result.calibration_blockers = cal_blockers
    if cal_blockers:
        blockers.extend(cal_blockers)
        result.production_allowed = False
        result.blockers = blockers
        return result

    # 2. Resolve expected dimension from calibration
    inventory = get_project_decision_inventory()
    for rec in inventory:
        if rec.decision_id == "rag.embedding_dimension_expected":
            expected_value = _optional_int(rec.current_value)
            if expected_value is not None:
                expected_dimension = expected_value
            break

    # 3. Check collection
    try:
        point_count = vector_store.size
        result.point_count = point_count
        result.collection_exists = True
        result.collection_empty = point_count == 0
    except QdrantConnectionError as exc:
        blockers.append(f"Qdrant unavailable: {exc}")
        result.blockers = blockers
        return result
    except Exception as exc:
        blockers.append(f"Cannot access vector store: {exc}")
        result.blockers = blockers
        return result

    if point_count == 0:
        blockers.append("Collection is empty")

    # 4. Check points / payload
    if point_count > 0:
        try:
            entries = vector_store.entries
            if entries:
                first = entries[0]
                result.embedding_dimension_actual = len(first.embedding)
                result.embedding_dimension_expected = expected_dimension or len(first.embedding)
                result.dimension_match = result.embedding_dimension_actual == result.embedding_dimension_expected
                result.corpus_version_found = first.corpus_version
                result.corpus_version_valid = first.corpus_version == CORPUS_VERSION

                # Check payload schema on first entry
                payload = {
                    "chunk_id": first.chunk_id,
                    "source_id": first.source_id,
                    "source_title": first.title,
                    "source_url": first.url or "",
                    "nvidia_technology": first.nvidia_technology,
                    "corpus_version": first.corpus_version,
                    "chunk_text": first.content,
                    "chunk_index": first.chunk_index,
                    "char_count": first.char_count,
                    "ingested_at": first.ingested_at,
                }
                missing = validate_payload_schema(payload)
                result.payload_schema_valid = len(missing) == 0
                if not result.payload_schema_valid:
                    blockers.append(f"Payload schema invalid: missing {missing}")

                # Count unique documents
                result.actual_document_count = _count_documents_in_store(vector_store)
                result.actual_chunk_count = point_count

                # Check dimension
                if not result.dimension_match:
                    blockers.append(
                        f"Embedding dimension mismatch: "
                        f"actual={result.embedding_dimension_actual}, "
                        f"expected={result.embedding_dimension_expected}"
                    )

                # Check corpus_version
                if not result.corpus_version_valid:
                    blockers.append(
                        f"Corpus version mismatch: found='{result.corpus_version_found}', expected='{CORPUS_VERSION}'"
                    )
        except Exception as exc:
            blockers.append(f"Cannot inspect vector store contents: {exc}")

    # 5. Check min_docs / min_chunks from calibration
    for rec in inventory:
        if rec.decision_id == "rag.min_corpus_documents":
            result.min_docs_calibrated = rec.production_allowed
            min_docs = _optional_int(rec.current_value)
            if rec.production_allowed and min_docs is not None:
                result.min_docs_met = result.actual_document_count >= min_docs
                if not result.min_docs_met:
                    blockers.append(f"Min documents not met: {result.actual_document_count} < {min_docs}")
        elif rec.decision_id == "rag.min_corpus_chunks":
            result.min_chunks_calibrated = rec.production_allowed
            min_chunks = _optional_int(rec.current_value)
            if rec.production_allowed and min_chunks is not None:
                result.min_chunks_met = result.actual_chunk_count >= min_chunks
                if not result.min_chunks_met:
                    blockers.append(f"Min chunks not met: {result.actual_chunk_count} < {min_chunks}")

    if not result.min_docs_calibrated:
        blockers.append("min_corpus_documents not calibrated")
    if not result.min_chunks_calibrated:
        blockers.append("min_corpus_chunks not calibrated")

    result.blockers = blockers
    result.production_allowed = len(blockers) == 0
    return result
