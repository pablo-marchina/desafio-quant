import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi

from app.rag.schemas import (
    HybridCandidate,
    NvidiaChunk,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]

KNOWLEDGE_BASE_DIR = BACKEND_DIR / "knowledge_base"
PROCESSED_DIR = KNOWLEDGE_BASE_DIR / "processed"
QDRANT_DIR = KNOWLEDGE_BASE_DIR / "qdrant"

CHUNKS_PATH = PROCESSED_DIR / "nvidia_chunks.json"

COLLECTION_NAME = "nvidia_knowledge_chunks"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

RRF_CONSTANT = 60

MAX_CANDIDATES_PER_TECHNOLOGY = 3
OVERFETCH_MULTIPLIER = 2

_embedding_model: Any | None = None


def tokenize(text: str) -> list[str]:
    return re.findall(
        r"[a-zA-ZÀ-ÿ0-9_-]+",
        text.casefold(),
    )


def load_chunks() -> list[NvidiaChunk]:
    if not CHUNKS_PATH.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                "A base NVIDIA ainda não foi ingerida. "
                "Execute POST /nvidia-rag/ingest primeiro."
            ),
        )

    data = json.loads(
        CHUNKS_PATH.read_text(encoding="utf-8")
    )

    return [
        NvidiaChunk.model_validate(item)
        for item in data
    ]


def get_embedding_model() -> Any:
    global _embedding_model

    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer(
                EMBEDDING_MODEL_NAME
            )
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Não foi possível carregar o modelo de embeddings: "
                    f"{error}"
                ),
            )

    return _embedding_model


def encode_documents(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()

    if hasattr(model, "encode_document"):
        vectors = model.encode_document(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    else:
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    return vectors.tolist()


def encode_query(query: str) -> list[float]:
    model = get_embedding_model()

    if hasattr(model, "encode_query"):
        vector = model.encode_query(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
    else:
        vector = model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

    return vector.tolist()


def get_qdrant_client() -> QdrantClient:
    QDRANT_DIR.mkdir(parents=True, exist_ok=True)

    return QdrantClient(
        path=str(QDRANT_DIR),
    )


def build_vector_index(
    chunks: list[NvidiaChunk],
) -> None:
    client = get_qdrant_client()

    try:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        vectors = encode_documents(
            [chunk.text for chunk in chunks]
        )

        vector_size = len(vectors[0])

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

        points = [
            models.PointStruct(
                id=index,
                vector=vector,
                payload=chunk.model_dump(mode="json"),
            )
            for index, (chunk, vector) in enumerate(
                zip(chunks, vectors),
                start=1,
            )
        ]

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
    finally:
        if hasattr(client, "close"):
            client.close()


def get_bm25_ranked_chunks(
    chunks: list[NvidiaChunk],
    query: str,
    limit: int,
) -> list[tuple[NvidiaChunk, float]]:
    corpus = [
        tokenize(
            " ".join(
                [
                    chunk.technology_name,
                    chunk.title,
                    " ".join(chunk.tags),
                    chunk.text,
                ]
            )
        )
        for chunk in chunks
    ]

    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(tokenize(query))

    ranked_indexes = sorted(
        range(len(chunks)),
        key=lambda index: scores[index],
        reverse=True,
    )[:limit]

    return [
        (chunks[index], float(scores[index]))
        for index in ranked_indexes
    ]


def get_semantic_ranked_chunks(
    query: str,
    limit: int,
) -> list[tuple[NvidiaChunk, float]]:
    client = get_qdrant_client()

    try:
        query_vector = encode_query(query)

        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )

        ranked_chunks = []

        for point in response.points:
            payload = point.payload or {}

            ranked_chunks.append(
                (
                    NvidiaChunk.model_validate(payload),
                    float(point.score),
                )
            )

        return ranked_chunks
    finally:
        if hasattr(client, "close"):
            client.close()


def diversify_candidates(
    candidates: list[HybridCandidate],
    limit: int,
) -> list[HybridCandidate]:
    selected: list[HybridCandidate] = []
    technology_counts: dict[str, int] = {}

    for candidate in candidates:
        if len(selected) >= limit:
            break

        current_count = technology_counts.get(
            candidate.technology_id,
            0,
        )

        if current_count >= MAX_CANDIDATES_PER_TECHNOLOGY:
            continue

        selected.append(candidate)

        technology_counts[candidate.technology_id] = (
            current_count + 1
        )

    return selected


def retrieve_hybrid(
    query: str,
    candidate_limit: int,
) -> list[HybridCandidate]:
    if candidate_limit <= 0:
        return []

    chunks = load_chunks()

    search_limit = max(
        candidate_limit,
        candidate_limit * OVERFETCH_MULTIPLIER,
    )

    lexical_results = get_bm25_ranked_chunks(
        chunks=chunks,
        query=query,
        limit=search_limit,
    )

    semantic_results = get_semantic_ranked_chunks(
        query=query,
        limit=search_limit,
    )

    lexical_scores = {
        chunk.chunk_id: score
        for chunk, score in lexical_results
    }

    semantic_scores = {
        chunk.chunk_id: score
        for chunk, score in semantic_results
    }

    chunks_by_id = {
        chunk.chunk_id: chunk
        for chunk in chunks
    }

    rrf_scores: dict[str, float] = {}

    for rank, (chunk, _) in enumerate(
        lexical_results,
        start=1,
    ):
        rrf_scores[chunk.chunk_id] = (
            rrf_scores.get(chunk.chunk_id, 0.0)
            + 1 / (RRF_CONSTANT + rank)
        )

    for rank, (chunk, _) in enumerate(
        semantic_results,
        start=1,
    ):
        rrf_scores[chunk.chunk_id] = (
            rrf_scores.get(chunk.chunk_id, 0.0)
            + 1 / (RRF_CONSTANT + rank)
        )

    candidates = []

    for chunk_id, fused_score in rrf_scores.items():
        chunk = chunks_by_id[chunk_id]

        candidates.append(
            HybridCandidate(
                chunk_id=chunk.chunk_id,
                technology_id=chunk.technology_id,
                technology_name=chunk.technology_name,
                title=chunk.title,
                text=chunk.text,
                source_url=chunk.source_url,
                source_type=chunk.source_type,
                tags=chunk.tags,
                lexical_score=lexical_scores.get(
                    chunk.chunk_id,
                    0.0,
                ),
                semantic_score=semantic_scores.get(
                    chunk.chunk_id,
                    0.0,
                ),
                fused_score=fused_score,
            )
        )

    candidates.sort(
        key=lambda candidate: candidate.fused_score,
        reverse=True,
    )

    return diversify_candidates(
        candidates=candidates,
        limit=candidate_limit,
    )