#!/usr/bin/env python3
"""Automated Qdrant corpus ingestion script.

Reads the local corpus (data/nvidia_corpus/), validates documents,
chunks, generates embeddings, and upserts to Qdrant with full provenance.

Usage:
    python scripts/ingest_nvidia_corpus.py --dry-run
    python scripts/ingest_nvidia_corpus.py --recreate-collection
    python scripts/ingest_nvidia_corpus.py --backend in_memory
    python scripts/ingest_nvidia_corpus.py --source-id nim triton
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag.embeddings import SentenceTransformerProvider  # noqa: E402
from src.rag.ingestion import (  # noqa: E402
    _CORPUS_DIR,
    _SOURCES_FILE,
    chunk_document,
    load_markdown_document,
    load_sources,
)
from src.rag.qdrant_store import QdrantConfig, QdrantConnectionError, QdrantStore  # noqa: E402
from src.rag.schemas import RagChunk  # noqa: E402
from src.rag.vector_store import InMemoryVectorStore, VectorEntry, VectorStore  # noqa: E402

# ---------------------------------------------------------------------------
# Report schema
# ---------------------------------------------------------------------------


@dataclass
class IngestionReport:
    ingestion_run_id: str
    documents_seen: int = 0
    documents_valid: int = 0
    documents_skipped: int = 0
    chunks_created: int = 0
    chunks_upserted: int = 0
    sources_failed: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    collection_name: str = ""
    backend: str = ""
    started_at: str = ""
    finished_at: str = ""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_document(
    md_path: Path,
    sources: dict[str, Any],
    fail_on_error: bool,
) -> list[str]:
    """Validate a single markdown document. Returns list of error messages."""
    errors: list[str] = []
    source_id = md_path.stem

    if source_id not in sources:
        errors.append(f"source_id '{source_id}' not found in sources.yaml")
    else:
        info = sources[source_id]
        if not info.get("title"):
            errors.append(f"source '{source_id}': title is required")
        if not info.get("product"):
            errors.append(f"source '{source_id}': product is required")
        if not info.get("gap_types"):
            errors.append(f"source '{source_id}': gap_types is required")
        if not info.get("version"):
            errors.append(f"source '{source_id}': version is required")
        if not info.get("document_type"):
            errors.append(f"source '{source_id}': document_type is required")
        if not info.get("content_hash"):
            errors.append(f"source '{source_id}': content_hash is required")
        if not info.get("last_checked_at"):
            errors.append(f"source '{source_id}': last_checked_at is required")
        if not info.get("valid_from"):
            errors.append(f"source '{source_id}': valid_from is required")
        if not info.get("freshness_policy"):
            errors.append(f"source '{source_id}': freshness_policy is required")
        if info.get("stale_after_days") is None:
            errors.append(f"source '{source_id}': stale_after_days is required")
        if info.get("is_active") is None:
            errors.append(f"source '{source_id}': is_active is required")

    if md_path.stat().st_size == 0:
        errors.append(f"file '{md_path.name}' is empty")

    if fail_on_error and errors:
        for err in errors:
            print(f"  VALIDATION ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    return errors


def load_sources_raw() -> dict[str, Any]:
    """Load sources.yaml as raw dict (including new fields)."""
    import yaml

    if not _SOURCES_FILE.exists():
        return {}
    raw = yaml.safe_load(_SOURCES_FILE.read_text(encoding="utf-8"))
    return cast(dict[str, Any], raw.get("sources", {}))


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


def compute_content_hash(raw_text: str) -> str:
    """Deterministic MD5 hash of the full document raw text."""
    return hashlib.md5(raw_text.encode("utf-8"), usedforsecurity=False).hexdigest()


def compute_chunk_hash(content: str) -> str:
    """Deterministic MD5 hash of a single chunk's content."""
    return hashlib.md5(content.encode("utf-8"), usedforsecurity=False).hexdigest()


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


def build_embedding_provider(
    *,
    model_name: str = "BAAI/bge-m3",
    require_real: bool = False,
) -> SentenceTransformerProvider:
    """Build a SentenceTransformer embedding provider."""
    try:
        provider = SentenceTransformerProvider(model_name)
        print(f"  Using SentenceTransformerProvider (dim={provider.vector_size})")
        return provider
    except ImportError:
        if require_real:
            raise
        print(
            "  WARNING: sentence-transformers not installed. " "Falling back to BAAI/bge-m3.",
            file=sys.stderr,
        )
        return SentenceTransformerProvider("BAAI/bge-m3")


# ---------------------------------------------------------------------------
# Vector store factory
# ---------------------------------------------------------------------------


def build_vector_store(args: argparse.Namespace) -> VectorStore:
    """Build vector store (Qdrant or InMemory)."""
    if args.backend == "in_memory":
        print("  Backend: InMemoryVectorStore")
        return InMemoryVectorStore()
    print(f"  Backend: QdrantStore (collection='{args.collection_name}')")
    config = QdrantConfig(
        url=args.qdrant_url,
        api_key=args.qdrant_api_key or None,
        collection_name=args.collection_name,
        vector_size=args.vector_size,
        timeout=args.qdrant_timeout,
    )
    try:
        store = QdrantStore(config=config)
        store._ensure_client()  # test connection
        return store
    except QdrantConnectionError as exc:
        print(f"  ERROR: Cannot connect to Qdrant: {exc}", file=sys.stderr)
        print("  HINT: Start Qdrant with: docker compose up -d qdrant", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------


def run_ingestion(args: argparse.Namespace) -> IngestionReport:
    """Run the full ingestion pipeline and return a report."""
    run_id = f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    started_at = datetime.now(UTC).isoformat()
    report = IngestionReport(
        ingestion_run_id=run_id,
        started_at=started_at,
        collection_name=args.collection_name,
        backend=args.backend,
    )

    # 1. Load sources
    print("Step 1/7: Loading sources...")
    raw_sources = load_sources_raw()
    sources = load_sources()
    if not sources:
        print("  No sources found. Nothing to ingest.")
        report.finished_at = datetime.now(UTC).isoformat()
        return report

    source_ids = list(sources.keys())
    print(f"  Found {len(source_ids)} sources: {', '.join(source_ids)}")

    # 2. Filter corpus files
    print("Step 2/7: Scanning corpus files...")
    md_files = sorted(_CORPUS_DIR.glob("*.md"))
    md_files = [f for f in md_files if f.name != "README.md"]
    md_files = [f for f in md_files if f.stem in raw_sources]

    if args.source_id:
        md_files = [f for f in md_files if f.stem in args.source_id]
    if args.product:
        md_files = [
            f
            for f in md_files
            if any(p.lower() in raw_sources.get(f.stem, {}).get("product", "").lower() for p in args.product)
        ]

    print(f"  Found {len(md_files)} document(s) to process")

    # 3. Validate documents
    print("Step 3/7: Validating documents...")
    valid_docs: list[tuple[Path, str]] = []  # (path, content_hash)
    for md_path in md_files:
        errors = validate_document(md_path, raw_sources, args.fail_on_validation_error)
        if errors:
            report.documents_skipped += 1
            report.sources_failed.append(md_path.stem)
            report.validation_errors.extend(f"{md_path.stem}: {e}" for e in errors)
            print(f"  SKIPPED {md_path.name}: {errors[0]}")
        else:
            raw_text = md_path.read_text(encoding="utf-8")
            content_hash = compute_content_hash(raw_text)
            valid_docs.append((md_path, content_hash))
            report.documents_valid += 1

    report.documents_seen = len(md_files)
    print(f"  Valid: {report.documents_valid}, Skipped: {report.documents_skipped}")

    # 4. Chunk documents
    print("Step 4/7: Chunking documents...")
    all_chunks: list[RagChunk] = []
    for md_path, content_hash in valid_docs:
        doc = load_markdown_document(md_path)
        if doc is None:
            continue
        doc_chunks = chunk_document(doc, sources)
        # Attach content_hash and chunk_hash
        for c in doc_chunks:
            c.content_hash = content_hash
        all_chunks.extend(doc_chunks)

    report.chunks_created = len(all_chunks)
    print(f"  Created {len(all_chunks)} chunk(s)")

    if not all_chunks:
        print("  No chunks to ingest.")
        report.finished_at = datetime.now(UTC).isoformat()
        return report

    # 5. Generate embeddings
    print("Step 5/7: Generating embeddings...")
    embedding_provider = build_embedding_provider(
        model_name=args.embedding_model,
        require_real=args.require_real_embeddings,
    )
    texts = [c.content for c in all_chunks]
    embeddings = embedding_provider.embed_batch(texts)
    print(f"  Generated {len(embeddings)} embedding(s)")

    # 6. Build vector entries
    print("Step 6/7: Building vector entries...")
    entries: list[VectorEntry] = []
    for chunk, emb in zip(all_chunks, embeddings, strict=True):
        chunk_hash = compute_chunk_hash(chunk.content)
        entries.append(
            VectorEntry(
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
                chunk_hash=chunk_hash,
                ingestion_run_id=run_id,
                previous_content_hash=chunk.previous_content_hash,
                collected_at=chunk.collected_at,
                last_checked_at=chunk.last_checked_at,
                valid_from=chunk.valid_from,
                valid_until=chunk.valid_until,
                freshness_policy=chunk.freshness_policy,
                stale_after_days=chunk.stale_after_days,
                is_active=chunk.is_active,
                deprecated_at=chunk.deprecated_at,
                superseded_by=chunk.superseded_by,
                deprecation_reason=chunk.deprecation_reason,
            )
        )

    # 7. Upsert to vector store
    print("Step 7/7: Upserting to vector store...")
    if args.dry_run:
        print("  DRY RUN — no upsert performed")
        report.chunks_upserted = 0
    else:
        store = build_vector_store(args)

        if args.recreate_collection:
            print("  Recreating collection...")
            store.clear()

        if args.skip_existing:
            to_upsert: list[VectorEntry] = []
            for e in entries:
                existing_entry = store.get_entry(e.chunk_id)
                if existing_entry is not None and existing_entry.chunk_hash == e.chunk_hash:
                    report.documents_skipped += 1
                else:
                    to_upsert.append(e)
            print(f"  Skipping {len(entries) - len(to_upsert)} unchanged chunk(s)")
            entries = to_upsert

        if entries:
            batch_size = args.batch_size
            for i in range(0, len(entries), batch_size):
                batch = entries[i : i + batch_size]
                store.add_entries(batch)
            report.chunks_upserted = len(entries)
            print(f"  Upserted {len(entries)} chunk(s) in batches of {batch_size}")
        else:
            report.chunks_upserted = 0
            print("  Nothing to upsert.")

    report.finished_at = datetime.now(UTC).isoformat()
    if not args.dry_run and args.backend == "qdrant" and report.documents_valid > 0:
        manifest = {
            "schema_version": 1,
            "ingestion_run_id": report.ingestion_run_id,
            "finished_at": report.finished_at,
            "collection_name": report.collection_name,
            "backend": report.backend,
            "embedding_model": args.embedding_model,
            "vector_size": args.vector_size,
            "documents_valid": report.documents_valid,
            "chunks_created": report.chunks_created,
            "chunks_upserted": report.chunks_upserted,
            "source_hashes": {path.stem: content_hash for path, content_hash in valid_docs},
        }
        manifest_path = _CORPUS_DIR / ".ingestion_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest NVIDIA corpus into Qdrant vector store",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and chunk but do not upsert",
    )
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Drop and recreate the collection before upsert",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip chunks whose chunk_hash already exists in the store",
    )
    parser.add_argument(
        "--source-id",
        nargs="+",
        default=None,
        help="Only process specific source IDs (e.g. nim triton)",
    )
    parser.add_argument(
        "--product",
        nargs="+",
        default=None,
        help="Only process specific product names",
    )
    parser.add_argument(
        "--fail-on-validation-error",
        action="store_true",
        help="Exit with code 1 if any document fails validation",
    )
    parser.add_argument(
        "--backend",
        choices=["qdrant", "in_memory"],
        default="qdrant",
        help="Vector store backend (default: qdrant)",
    )
    parser.add_argument(
        "--collection-name",
        default=None,
        help="Qdrant collection name (default: nvidia_corpus)",
    )
    parser.add_argument(
        "--qdrant-url",
        default=None,
        help="Qdrant URL (default: env QDRANT_URL or http://localhost:6333)",
    )
    parser.add_argument(
        "--qdrant-api-key",
        default=None,
        help="Qdrant API key (default: env QDRANT_API_KEY)",
    )
    parser.add_argument(
        "--qdrant-timeout",
        type=int,
        default=10,
        help="Qdrant client timeout seconds (default: 10)",
    )
    parser.add_argument(
        "--vector-size",
        type=int,
        default=None,
        help="Qdrant vector dimension (default: env QDRANT_VECTOR_SIZE or 384)",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="SentenceTransformer model (default: env RAG_EMBEDDING_MODEL or BAAI/bge-m3)",
    )
    parser.add_argument(
        "--require-real-embeddings",
        action="store_true",
        help="Fail if sentence-transformers is not installed.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Number of chunks per upsert batch (default: 32)",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Save ingestion report to this path (JSON)",
    )
    args = parser.parse_args(argv)
    import os

    args.collection_name = args.collection_name or os.getenv("QDRANT_COLLECTION", "nvidia_corpus")
    args.qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
    args.qdrant_api_key = args.qdrant_api_key if args.qdrant_api_key is not None else os.getenv("QDRANT_API_KEY", "")
    args.vector_size = args.vector_size or int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))
    args.embedding_model = args.embedding_model or os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-m3")
    return args


def print_report(report: IngestionReport) -> None:
    """Print a human-readable ingestion report."""
    print()
    print("=" * 60)
    print("INGESTION REPORT")
    print("=" * 60)
    print(f"  Run ID:              {report.ingestion_run_id}")
    print(f"  Started:             {report.started_at}")
    print(f"  Finished:            {report.finished_at}")
    print(f"  Documents seen:      {report.documents_seen}")
    print(f"  Documents valid:     {report.documents_valid}")
    print(f"  Documents skipped:   {report.documents_skipped}")
    print(f"  Chunks created:      {report.chunks_created}")
    print(f"  Chunks upserted:     {report.chunks_upserted}")
    print(f"  Sources failed:      {report.sources_failed or 'none'}")
    print(f"  Validation errors:   {len(report.validation_errors)}")
    for err in report.validation_errors[:5]:
        print(f"    - {err}")
    if len(report.validation_errors) > 5:
        print(f"    ... and {len(report.validation_errors) - 5} more")
    print(f"  Collection:          {report.collection_name}")
    print(f"  Backend:             {report.backend}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    print("NVIDIA Corpus Ingestion")
    print(f"  Corpus: {_CORPUS_DIR}")
    print(f"  Sources: {_SOURCES_FILE}")
    if args.dry_run:
        print("  Mode: DRY RUN (no upsert)")
    print()

    report = run_ingestion(args)
    print_report(report)

    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(asdict(report), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Report saved to: {report_path}")

    if report.validation_errors and args.fail_on_validation_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
