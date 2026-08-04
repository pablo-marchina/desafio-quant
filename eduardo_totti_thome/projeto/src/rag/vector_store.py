"""Cliente do Qdrant + gestão da coleção de vetores."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from rag.embeddings import EMBEDDING_DIM

load_dotenv()

# Nome da "tabela de vetores" onde os documentos NVIDIA vão morar.
COLLECTION_NAME = "nvidia_docs"


def get_client() -> QdrantClient:
    """Conecta no Qdrant usando a URL do .env (padrão: localhost:6333)."""
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    return QdrantClient(url=url)

def ensure_collection(client: QdrantClient) -> None:
    """Cria a coleção se ela ainda não existir.

    Vetores de 384 dimensões, comparados por similaridade de cosseno.
    Se a coleção já existe, não faz nada (não apaga o que estiver lá).
    """
    if client.collection_exists(COLLECTION_NAME):
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
