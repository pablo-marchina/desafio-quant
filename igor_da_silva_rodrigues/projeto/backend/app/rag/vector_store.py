from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from qdrant_client import QdrantClient, models

from app.core.contracts import validate_contract
from app.core.schemas import KnowledgeChunk, RetrievedChunk
from app.rag.config import RAGConfig
from app.rag.embeddings import BM25SparseProvider, DenseEmbeddingProvider, create_dense_provider


DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"


class QdrantKnowledgeStore:
    def __init__(
        self,
        config: RAGConfig | None = None,
        client: QdrantClient | None = None,
        dense_provider: DenseEmbeddingProvider | None = None,
        sparse_provider: Any | None = None,
    ) -> None:
        self.config = config or RAGConfig.from_env()
        self.client = client or QdrantClient(
            url=self.config.qdrant_url,
            api_key=self.config.qdrant_api_key,
            timeout=30,
        )
        self.dense = dense_provider or create_dense_provider(self.config)
        self.sparse = sparse_provider or BM25SparseProvider(self.config.sparse_model)

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.config.collection_name):
            self._validate_collection_dimension()
            return
        self.client.create_collection(
            collection_name=self.config.collection_name,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=self.dense.dimension,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )

    def upsert_chunks(self, chunks: Sequence[KnowledgeChunk], batch_size: int = 100) -> int:
        if not chunks:
            return 0
        self.ensure_collection()
        inserted = 0
        for start in range(0, len(chunks), batch_size):
            batch = list(chunks[start : start + batch_size])
            dense_vectors = self.dense.embed_documents([chunk.content for chunk in batch])
            sparse_vectors = self.sparse.embed_documents([chunk.content for chunk in batch])
            points = []
            for chunk, dense, sparse in zip(batch, dense_vectors, sparse_vectors, strict=True):
                payload = {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "metadata": chunk.metadata.model_dump(mode="json"),
                }
                points.append(
                    models.PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                        vector={DENSE_VECTOR: dense, SPARSE_VECTOR: sparse},
                        payload=payload,
                    )
                )
            self.client.upsert(
                collection_name=self.config.collection_name,
                points=points,
                wait=True,
            )
            inserted += len(points)
        return inserted

    def hybrid_search(
        self,
        query: str,
        top_k: int | None = None,
        profile: str | None = None,
    ) -> list[RetrievedChunk]:
        limit = top_k or self.config.top_k
        dense_query = self.dense.embed_query(query)
        sparse_query = self.sparse.embed_query(query)
        profile_filter = _profile_filter(profile)
        response = self.client.query_points(
            collection_name=self.config.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_query,
                    using=DENSE_VECTOR,
                    filter=profile_filter,
                    limit=limit,
                ),
                models.Prefetch(
                    query=sparse_query,
                    using=SPARSE_VECTOR,
                    filter=profile_filter,
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=profile_filter,
            limit=limit,
            with_payload=True,
        )
        results = []
        for point in response.points:
            payload = point.payload or {}
            candidate = {
                "chunk_id": payload.get("chunk_id", str(point.id)),
                "content": payload.get("content", ""),
                "metadata": payload.get("metadata", {}),
                "retrieval_score": float(point.score),
            }
            results.append(validate_contract(RetrievedChunk, candidate))
        return results

    def _validate_collection_dimension(self) -> None:
        collection = self.client.get_collection(self.config.collection_name)
        vectors = collection.config.params.vectors
        dense_config = vectors.get(DENSE_VECTOR) if isinstance(vectors, dict) else vectors
        current_size = getattr(dense_config, "size", None)
        if current_size is not None and current_size != self.dense.dimension:
            raise ValueError(
                f"Coleção {self.config.collection_name} usa dimensão {current_size}, "
                f"mas o embedding configurado usa {self.dense.dimension}"
            )


def _profile_filter(profile: str | None) -> models.Filter | None:
    if not profile or profile == "Non-AI":
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.perfil_aplicavel",
                match=models.MatchValue(value=profile),
            )
        ]
    )
