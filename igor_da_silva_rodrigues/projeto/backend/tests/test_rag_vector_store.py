import zlib

from qdrant_client import QdrantClient, models

from app.core.schemas import KnowledgeChunk, KnowledgeMetadata
from app.rag.config import RAGConfig
from app.rag.vector_store import QdrantKnowledgeStore


class FakeDense:
    dimension = 4

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        lower = text.lower()
        return [
            float("triton" in lower),
            float("nemo" in lower),
            float("latencia" in lower),
            0.1,
        ]


class FakeSparse:
    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        tokens = sorted(set(text.lower().split()))
        indices = [zlib.crc32(token.encode("utf-8")) for token in tokens]
        return models.SparseVector(indices=indices, values=[1.0] * len(indices))


def _chunk(chunk_id, technology, content, profiles):
    return KnowledgeChunk(
        chunk_id=chunk_id,
        content=content,
        metadata=KnowledgeMetadata(
            tecnologia=technology,
            tipo="documentacao",
            dores_relacionadas=["latencia"],
            perfil_aplicavel=profiles,
            titulo_secao="Visao geral",
            url_fonte=f"https://docs.nvidia.com/{technology.lower()}",
        ),
    )


def test_qdrant_store_upserts_and_runs_hybrid_search_with_profile_filter():
    config = RAGConfig(collection_name="test_nvidia", top_k=20, top_n=5)
    store = QdrantKnowledgeStore(
        config=config,
        client=QdrantClient(":memory:"),
        dense_provider=FakeDense(),
        sparse_provider=FakeSparse(),
    )
    chunks = [
        _chunk("triton-1", "Triton", "Triton reduz latencia de inferencia", ["AI-native"]),
        _chunk("nemo-1", "NeMo", "NeMo permite customizar modelos", ["AI-enabled"]),
    ]

    inserted = store.upsert_chunks(chunks)
    results = store.hybrid_search("Triton latencia", profile="AI-native")

    assert inserted == 2
    assert results
    assert all(item.metadata.tecnologia == "Triton" for item in results)
    assert results[0].content == "Triton reduz latencia de inferencia"
