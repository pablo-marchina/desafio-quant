"""Persistencia e busca vetorial no Qdrant.

Implementacao V3 do contrato publico ``VectorRepository``. A colecao e'
criada de forma idempotente no primeiro upsert, usando a dimensao do vetor
inserido — ainda nao ha gestao antecipada de schema porque nenhum vetor
real foi persistido antes desta versao.
"""

from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from apps.api.src.modules.embeddings.application.dto import (
    ChunkEmbeddingRecord,
    ChunkSearchResult,
)
from apps.api.src.modules.embeddings.application.public.vector_repository import (
    VectorRepository,
)
from apps.api.src.modules.embeddings.domain.exceptions import (
    EmbeddingCollectionSchemaMismatchError,
)


class QdrantVectorRepository(VectorRepository):
    """Persiste e busca vetores de chunks em uma colecao do Qdrant."""

    def __init__(self, *, url: str, collection_name: str) -> None:
        self._client = AsyncQdrantClient(url=url)
        self._collection_name = collection_name

    async def upsert(self, record: ChunkEmbeddingRecord) -> None:
        await self._ensure_collection(record.dimension, record.model_name)
        await self._client.upsert(
            collection_name=self._collection_name,
            points=[
                PointStruct(
                    id=str(record.chunk_id),
                    vector=list(record.values),
                    payload={
                        "document_id": str(record.document_id),
                        "source_url": record.source_url,
                        "source_type": record.source_type,
                        "model_name": record.model_name,
                    },
                )
            ],
        )

    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        source_type: str | None = None,
        document_ids: list[UUID] | None = None,
    ) -> list[ChunkSearchResult]:
        if document_ids is not None and len(document_ids) == 0:
            return []
        response = await self._client.query_points(
            collection_name=self._collection_name,
            query=list(query_vector),
            query_filter=self._build_filter(source_type, document_ids),
            limit=limit,
        )
        return [
            ChunkSearchResult(
                chunk_id=UUID(str(point.id)),
                document_id=UUID(point.payload["document_id"]),
                source_url=point.payload["source_url"],
                source_type=point.payload.get("source_type", "startup_evidence"),
                score=point.score,
            )
            for point in response.points
        ]

    async def get_by_chunk_id(self, chunk_id: UUID) -> ChunkEmbeddingRecord | None:
        if not await self._client.collection_exists(self._collection_name):
            return None

        points = await self._client.retrieve(
            collection_name=self._collection_name,
            ids=[str(chunk_id)],
            with_vectors=True,
        )
        if not points:
            return None

        point = points[0]
        values = tuple(point.vector)
        return ChunkEmbeddingRecord(
            chunk_id=chunk_id,
            document_id=UUID(point.payload["document_id"]),
            source_url=point.payload["source_url"],
            source_type=point.payload.get("source_type", "startup_evidence"),
            values=values,
            dimension=len(values),
            model_name=point.payload["model_name"],
        )

    async def delete_by_document_id(self, document_id: UUID) -> None:
        if not await self._client.collection_exists(self._collection_name):
            return

        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    )
                ]
            ),
        )

    def _build_filter(
        self,
        source_type: str | None,
        document_ids: list[UUID] | None = None,
    ) -> Filter | None:
        conditions = []
        if source_type is not None:
            conditions.append(
                FieldCondition(key="source_type", match=MatchValue(value=source_type))
            )
        if document_ids is not None:
            conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=[str(did) for did in document_ids]),
                )
            )
        if not conditions:
            return None
        return Filter(must=conditions)

    async def _ensure_collection(self, dimension: int, model_name: str) -> None:
        if not await self._client.collection_exists(self._collection_name):
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
                metadata={
                    "embedding_dimension": dimension,
                    "embedding_model_name": model_name,
                },
            )
            return

        collection = await self._client.get_collection(self._collection_name)
        vectors = collection.config.params.vectors
        collection_dimension = getattr(vectors, "size", None)
        metadata = collection.config.metadata or {}
        collection_model_name = metadata.get("embedding_model_name")

        if collection_dimension != dimension:
            raise EmbeddingCollectionSchemaMismatchError(
                "A colecao Qdrant usa dimensao "
                f"{collection_dimension}, mas o modelo {model_name!r} gerou "
                f"dimensao {dimension}. Crie ou reindexe uma colecao compativel."
            )
        if collection_model_name is None:
            raise EmbeddingCollectionSchemaMismatchError(
                "A colecao Qdrant existente nao declara o modelo de embedding. "
                "Reindexe os vetores em uma colecao com metadata de schema antes "
                "de continuar a gravar."
            )
        if collection_model_name != model_name:
            raise EmbeddingCollectionSchemaMismatchError(
                "A colecao Qdrant usa o modelo "
                f"{collection_model_name!r}, mas a escrita usa {model_name!r}. "
                "Crie ou reindexe uma colecao compativel."
            )
