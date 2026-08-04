"""Recuperação: dada uma pergunta, busca os chunks mais relevantes no Qdrant."""

from __future__ import annotations

from qdrant_client import QdrantClient

from rag.embeddings import embed_query
from rag.vector_store import COLLECTION_NAME


def search(client: QdrantClient, query: str, limit: int = 3) -> list[dict]:
    """Vetoriza a pergunta, busca no Qdrant e devolve os top trechos.

    Cada item devolvido é um dict: {score, technology, source_url, text}.
    """
    query_vector = embed_query(query)
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )
    
    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            {
                "score": point.score,
                "technology": payload.get("technology"),
                "source_url": payload.get("source_url"),
                "text": payload.get("text"),
            }
        )
    return results

