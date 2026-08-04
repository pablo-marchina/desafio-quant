from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from radar.rag.embeddings import EMBEDDING_DIMENSION, embed_batch

COLLECTION_NAME = "nvidia_knowledge"


class VectorStore:
    """Qdrant in-memory vector store for NVIDIA knowledge chunks."""

    def __init__(self) -> None:
        self._client = QdrantClient(location=":memory:")
        self._collection_created = False

    def _ensure_collection(self) -> None:
        if self._collection_created:
            return
        if self._client.collection_exists(COLLECTION_NAME):
            self._client.delete_collection(COLLECTION_NAME)
        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        self._collection_created = True

    def insert(self, chunks: list[dict[str, Any]]) -> int:
        self._ensure_collection()
        if not chunks:
            return 0

        texts = [chunk["content"] for chunk in chunks]
        vectors = embed_batch(texts)

        points = [
            PointStruct(
                id=chunk.get("id", i + 1),
                vector=vectors[i],
                payload=chunk,
            )
            for i, chunk in enumerate(chunks)
        ]

        self._client.upsert(collection_name=COLLECTION_NAME, points=points)
        return len(points)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self._collection_created:
            return []

        from radar.rag.embeddings import embed_text

        query_vector = embed_text(query)

        results = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                **(hit.payload or {}),
            }
            for hit in results.points
        ]

    def count(self) -> int:
        if not self._collection_created:
            return 0
        return self._client.count(collection_name=COLLECTION_NAME).count

    def clear(self) -> None:
        self._collection_created = False
        self._client.close()
        self._client = QdrantClient(location=":memory:")
