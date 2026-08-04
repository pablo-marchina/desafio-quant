"""Corpus ingestion pipeline: load → chunk → embed → upsert Qdrant.

Usage:
    python scripts/run_qdrant_ingestion.py
    python scripts/run_qdrant_ingestion.py --url http://localhost:6333 --collection nvidia_corpus

Requires Qdrant running (``docker compose up qdrant``) and
``sentence-transformers`` installed (``pip install -e ".[rag]"``).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from typing import Any

from src.rag.embeddings import SentenceTransformerProvider
from src.rag.ingestion import load_and_chunk_corpus
from src.rag.qdrant_store import QdrantConnectionError, build_qdrant_store
from src.rag.vector_store import VectorEntry


def _make_vector_entries(
    chunks: list[Any],
    embedding_model: SentenceTransformerProvider,
    run_id: str,
) -> list[VectorEntry]:
    texts = [c.content for c in chunks]
    embeddings = embedding_model.embed_batch(texts)
    now_iso = datetime.now(UTC).isoformat()
    entries: list[VectorEntry] = []
    for chunk, emb in zip(chunks, embeddings, strict=False):
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
                document_type=chunk.document_type or "nvidia_corpus",
                content_hash=chunk.content_hash,
                collected_at=now_iso,
                is_active=chunk.is_active if hasattr(chunk, "is_active") else True,
                ingestion_run_id=run_id,
            )
        )
    return entries


def run_ingestion(
    *,
    url: str = "http://localhost:6333",
    collection_name: str = "nvidia_corpus",
    vector_size: int = 384,
    api_key: str | None = None,
    clear_existing: bool = False,
    batch_size: int = 100,
) -> dict[str, Any]:
    print(f"Connecting to Qdrant at {url} ...")
    store = build_qdrant_store(
        url=url,
        collection_name=collection_name,
        vector_size=vector_size,
        api_key=api_key,
    )

    if clear_existing:
        print("Clearing existing collection ...")
        store.clear()

    print("Loading embedding model (all-MiniLM-L6-v2) ...")
    emb = SentenceTransformerProvider(model_name="all-MiniLM-L6-v2")
    print(f"  Vector size: {emb.vector_size}")

    print("Loading and chunking corpus from data/nvidia_corpus/ ...")
    chunks = load_and_chunk_corpus()
    print(f"  Total chunks: {len(chunks)}")

    if not chunks:
        return {
            "status": "skipped",
            "chunk_count": 0,
            "entry_count": 0,
            "message": "No chunks found — corpus is empty.",
        }

    run_id = f"ingestion-{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    entries = _make_vector_entries(chunks, emb, run_id)
    print(f"  Generated {len(entries)} vector entries")

    print(f"Upserting to Qdrant collection '{collection_name}' ...")
    total = len(entries)
    for i in range(0, total, batch_size):
        batch = entries[i : i + batch_size]
        store.add_entries(batch)
        pct = min(100, round((i + len(batch)) / total * 100))
        print(f"  Progress: {i + len(batch)}/{total} ({pct}%)")

    final_size = store.size
    print(f"  Done! Collection size: {final_size}")

    return {
        "status": "completed",
        "chunk_count": len(chunks),
        "entry_count": len(entries),
        "collection_size": final_size,
        "collection_name": collection_name,
        "run_id": run_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NVIDIA corpus into Qdrant")
    parser.add_argument("--url", default="http://localhost:6333", help="Qdrant URL")
    parser.add_argument("--collection", default="nvidia_corpus", help="Qdrant collection name")
    parser.add_argument("--vector-size", type=int, default=384, help="Embedding dimension")
    parser.add_argument("--api-key", default=None, help="Qdrant API key")
    parser.add_argument("--clear", action="store_true", help="Clear existing collection before ingest")
    parser.add_argument("--batch-size", type=int, default=100, help="Upsert batch size")
    args = parser.parse_args()

    try:
        result = run_ingestion(
            url=args.url,
            collection_name=args.collection,
            vector_size=args.vector_size,
            api_key=args.api_key,
            clear_existing=args.clear,
            batch_size=args.batch_size,
        )
        print(f"\nIngestion {result['status']}:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    except QdrantConnectionError as exc:
        print(f"ERROR: Cannot connect to Qdrant at {args.url}: {exc}", file=sys.stderr)
        print("  Is Qdrant running? Try: docker compose up qdrant", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
