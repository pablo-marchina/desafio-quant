from uuid import uuid5, NAMESPACE_URL
from datetime import datetime, timezone
from typing import Any

from requests import RequestException

from app.rag.chunking import chunk_text
from app.rag.embeddings import EmbeddingProvider
from app.rag.freshness import content_hash, extract_meta_date, parse_http_date
from app.rag.seed_data import NVIDIA_TECHNOLOGY_DOCS
from app.rag.vector_store import QdrantHttpClient
from app.scraping import fetch_public_website_text


def startup_evidence_point_id(
    *,
    analysis_run_id: str,
    source_url: str,
    chunk_index: int,
) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"startup:{analysis_run_id}:{source_url}#{chunk_index}",
        )
    )


def embed_passage(embedder: EmbeddingProvider, text: str) -> list[float]:
    return (
        embedder.embed_passage(text)
        if hasattr(embedder, "embed_passage")
        else embedder.embed(text)
    )


def ingest_nvidia_seed_documents(
    vector_store: QdrantHttpClient,
    embedder: EmbeddingProvider,
    collection_name: str,
    reset_collection: bool = False,
) -> dict[str, int]:
    vector_store.ensure_collection(collection_name, recreate=reset_collection)

    points = []

    for document in NVIDIA_TECHNOLOGY_DOCS:
        chunks = chunk_text(document["text"])
        for chunk in chunks:
            point_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{document['source_url']}#{chunk.chunk_index}",
                )
            )
            points.append(
                {
                    "id": point_id,
                    "vector": embed_passage(embedder, chunk.text),
                    "payload": {
                        "product_name": document["product_name"],
                        "category": document["category"],
                        "source_type": "seed",
                        "source_url": document["source_url"],
                        "summary": document["summary"],
                        "chunk_index": chunk.chunk_index,
                        "chunk_text": chunk.text,
                    },
                }
            )

    vector_store.upsert_points(collection_name, points)
    return {"documents": len(NVIDIA_TECHNOLOGY_DOCS), "chunks": len(points)}


def ingest_nvidia_official_pages(
    vector_store: QdrantHttpClient,
    embedder: EmbeddingProvider,
    collection_name: str,
    reset_collection: bool = False,
    max_chars_per_source: int = 12000,
    max_chunks_per_source: int = 6,
    documents: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    vector_store.ensure_collection(collection_name, recreate=reset_collection)

    points = []
    sources = []
    collected_at = datetime.now(timezone.utc).isoformat()

    for document in documents or NVIDIA_TECHNOLOGY_DOCS:
        source_url = document["source_url"]
        try:
            fetched = fetch_public_website_text(
                source_url,
                max_chars=max_chars_per_source,
            )
            text = fetched["text"]
            if len(text) < 120:
                raise ValueError("Texto extraido ficou curto demais para ingestao.")

            fetched_hash = content_hash(text)
            modified_at = parse_http_date(
                (fetched.get("headers") or {}).get("Last-Modified")
            ) or extract_meta_date(str(fetched.get("html") or ""))
            chunks = chunk_text(text)[:max_chunks_per_source]
            for chunk in chunks:
                point_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"official:{fetched['source_url']}#{chunk.chunk_index}",
                    )
                )
                points.append(
                    {
                        "id": point_id,
                        "vector": embed_passage(embedder, chunk.text),
                        "payload": {
                            "product_name": document["product_name"],
                            "category": document["category"],
                            "source_type": "official_page",
                            "source_url": fetched["source_url"],
                            "summary": document["summary"],
                            "chunk_index": chunk.chunk_index,
                            "chunk_text": chunk.text,
                            "collected_at": collected_at,
                            "content_hash": fetched_hash,
                            "modified_at": modified_at,
                            "characters": fetched["characters"],
                        },
                    }
                )

            sources.append(
                {
                    "product_name": document["product_name"],
                    "source_url": fetched["source_url"],
                    "status": "collected",
                    "category": document["category"],
                    "characters": fetched["characters"],
                    "chunks": len(chunks),
                    "content_hash": fetched_hash,
                    "modified_at": modified_at,
                    "collected_at": collected_at,
                    "error": None,
                }
            )
        except (RequestException, ValueError) as error:
            fallback_chunks = chunk_text(document["text"])[:max_chunks_per_source]
            fallback_hash = content_hash(document["text"])
            for chunk in fallback_chunks:
                point_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"seed-fallback:{source_url}#{chunk.chunk_index}",
                    )
                )
                points.append(
                    {
                        "id": point_id,
                        "vector": embed_passage(embedder, chunk.text),
                        "payload": {
                            "product_name": document["product_name"],
                            "category": document["category"],
                            "source_type": "seed_fallback",
                            "source_url": source_url,
                            "summary": document["summary"],
                            "chunk_index": chunk.chunk_index,
                            "chunk_text": chunk.text,
                            "collected_at": collected_at,
                            "content_hash": fallback_hash,
                            "modified_at": None,
                            "characters": len(document["text"]),
                        },
                    }
                )
            sources.append(
                {
                    "product_name": document["product_name"],
                    "source_url": source_url,
                    "status": "fallback_seed",
                    "category": document["category"],
                    "characters": len(document["text"]),
                    "chunks": len(fallback_chunks),
                    "content_hash": fallback_hash,
                    "modified_at": None,
                    "collected_at": collected_at,
                    "error": str(error),
                }
            )

    vector_store.upsert_points(collection_name, points)
    return {
        "collection_name": collection_name,
        "documents": sum(
            1
            for source in sources
            if source["status"] in {"collected", "fallback_seed"}
        ),
        "chunks": len(points),
        "sources": sources,
        "collected_at": collected_at,
    }


def ingest_startup_evidence_pages(
    vector_store: QdrantHttpClient,
    embedder: EmbeddingProvider,
    collection_name: str,
    startup_name: str,
    analysis_run_id: str,
    pages: list[dict[str, Any]],
    website_url: str | None = None,
    max_chunks_per_page: int = 8,
) -> dict[str, object]:
    vector_store.ensure_collection(collection_name)

    points = []
    collected_at = datetime.now(timezone.utc).isoformat()

    for page in pages:
        text = str(page.get("text") or "")
        source_url = str(page.get("source_url") or website_url or "")
        if len(text) < 80 or not source_url:
            continue

        chunks = chunk_text(text)[:max_chunks_per_page]
        for chunk in chunks:
            point_id = startup_evidence_point_id(
                analysis_run_id=analysis_run_id,
                source_url=source_url,
                chunk_index=chunk.chunk_index,
            )
            points.append(
                {
                    "id": point_id,
                    "vector": embed_passage(embedder, chunk.text),
                    "payload": {
                        "startup_name": startup_name,
                        "analysis_run_id": analysis_run_id,
                        "website_url": website_url,
                        "source_type": "startup_page",
                        "source_url": source_url,
                        "title": page.get("title"),
                        "status_code": page.get("status_code"),
                        "characters": page.get("characters", len(text)),
                        "chunk_index": chunk.chunk_index,
                        "chunk_text": chunk.text,
                        "collected_at": collected_at,
                        "page_collected_at": page.get("collected_at"),
                    },
                }
            )

    vector_store.upsert_points(collection_name, points)
    return {
        "collection_name": collection_name,
        "startup_name": startup_name,
        "analysis_run_id": analysis_run_id,
        "pages": len(pages),
        "chunks": len(points),
        "collected_at": collected_at,
    }
