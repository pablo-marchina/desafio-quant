from __future__ import annotations

from qdrant_client.models import Distance, VectorParams

from rag.client import get_client

COLLECTION_NAME = "nvidia_knowledge"
EMBEDDING_DIM = 3072  # dimensão do gemini-embedding-001


def criar_collection() -> None:
    client = get_client()
    collections = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in collections:
        print(f"Collection '{COLLECTION_NAME}' já existe.")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    print(f"Collection '{COLLECTION_NAME}' criada com sucesso.")


if __name__ == "__main__":
    criar_collection()
