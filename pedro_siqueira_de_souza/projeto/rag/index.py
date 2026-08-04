"""Indexação do corpus NVIDIA no Qdrant (RAG — Entregável 3).

Pega o corpus extraído (`rag/corpus/nvidia_docs.jsonl`), quebra em chunks
(`rag.chunk`), gera embeddings (`core.embeddings`) e grava cada chunk como um
PONTO no Qdrant — vetor + payload (tech, url, texto). É essa coleção que o
retriever (próximo passo) consulta.

Decisões de design:
  - Client e embeddings são INJETÁVEIS (parâmetros): em produção usam o Qdrant
    real (`settings.qdrant_url`) e a OpenAI; nos testes usam `QdrantClient(
    ":memory:")` + embeddings falsos — sem rede, sem chave, sem container.
  - A coleção é RECRIADA a cada indexação: o corpus é pequeno e isso garante
    idempotência (rodar de novo não duplica pontos). Para corpora grandes,
    valeria upsert incremental — fora de escopo agora.
  - Dimensão do vetor é DESCOBERTA do primeiro embedding, não hardcoded: troca
    de `EMBEDDING_MODEL` não quebra a criação da coleção.
  - Distância COSINE: padrão para embeddings de texto normalizados.
"""
import json
from pathlib import Path

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from core.config import settings
from rag.chunk import Chunk, chunk_corpus
from rag.ingest import CORPUS_PATH, NvidiaDoc

COLLECTION_NAME = "nvidia_kb"


def get_qdrant_client() -> QdrantClient:
    """Cliente para o Qdrant real (docker-compose / serviço configurado)."""
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )


def load_corpus(path: Path = CORPUS_PATH) -> list[NvidiaDoc]:
    """Lê o JSONL gerado pela ingestão de volta para objetos NvidiaDoc."""
    if not path.exists():
        raise FileNotFoundError(
            f"Corpus não encontrado em {path}. Rode `python -m rag.ingest` antes."
        )
    docs: list[NvidiaDoc] = []
    with path.open(encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                docs.append(NvidiaDoc(**json.loads(linha)))
    return docs


def _ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    """(Re)cria a coleção com a dimensão certa. Idempotente por recriação."""
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )


def index_chunks(
    chunks: list[Chunk],
    client: QdrantClient,
    embeddings,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Embeda os chunks e os grava como pontos no Qdrant. Retorna a contagem.

    `embeddings` só precisa expor `embed_documents(list[str]) -> list[list[float]]`
    (interface do LangChain) — por isso aceita o objeto real ou um falso no teste.
    """
    if not chunks:
        logger.warning("index: nenhum chunk para indexar.")
        return 0

    textos = [c.text for c in chunks]
    vetores = embeddings.embed_documents(textos)
    _ensure_collection(client, collection_name, dim=len(vetores[0]))

    pontos = [
        PointStruct(
            id=i,
            vector=vetor,
            payload={
                "tech": chunk.tech,
                "url": chunk.url,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
            },
        )
        for i, (chunk, vetor) in enumerate(zip(chunks, vetores))
    ]
    client.upsert(collection_name=collection_name, points=pontos)
    logger.info("index: {} chunks indexados em '{}'", len(pontos), collection_name)
    return len(pontos)


def build_index(
    corpus_path: Path = CORPUS_PATH,
    client: QdrantClient | None = None,
    embeddings=None,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Pipeline completo: corpus -> chunks -> embeddings -> Qdrant."""
    from core.embeddings import get_embeddings

    client = client or get_qdrant_client()
    embeddings = embeddings or get_embeddings()

    docs = load_corpus(corpus_path)
    chunks = chunk_corpus(docs)
    logger.info("index: {} docs -> {} chunks", len(docs), len(chunks))
    return index_chunks(chunks, client, embeddings, collection_name)


if __name__ == "__main__":
    # Execução manual — exige Qdrant de pé (docker compose up -d qdrant) e
    # OPENAI_API_KEY no .env (gera embeddings reais, tem custo).
    total = build_index()
    print(f"\nIndexação concluída: {total} chunks na coleção '{COLLECTION_NAME}'.")
