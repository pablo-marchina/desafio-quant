"""Retrieval vetorial da base NVIDIA (RAG — Entregável 3, baseline SEM rerank).

É o estágio que roda A CADA consulta: pega uma pergunta em texto, transforma no
MESMO espaço vetorial usado na indexação (`core.embeddings`) e pede ao Qdrant os
`top_k` chunks mais próximos por cosseno. Cada resultado carrega a proveniência
(tech + url) — é o que vira CITAÇÃO no briefing.

Por que SEM reranking ainda? O projeto (Entregável 3) pede medir a qualidade
do retrieval puro primeiro e só depois adicionar o Cohere Rerank, para enxergar
o ganho que ele traz. Este módulo é esse baseline; o reranker entra no próximo
commit, embrulhando estes resultados.

Decisões de design:
  - Client e embeddings INJETÁVEIS (igual ao index): produção usa Qdrant real +
    OpenAI; testes usam `QdrantClient(":memory:")` + embeddings falsos.
  - O modelo de embedding TEM de ser o mesmo da indexação — por isso ambos os
    módulos pedem em `core.embeddings.get_embeddings` (centralização evita o bug
    de comparar vetores de modelos diferentes).
"""
from loguru import logger
from pydantic import BaseModel
from qdrant_client import QdrantClient

from rag.index import COLLECTION_NAME, get_qdrant_client

DEFAULT_TOP_K = 5


class RetrievedChunk(BaseModel):
    """Um chunk recuperado, com o score de similaridade e a proveniência."""

    tech: str
    url: str
    text: str
    chunk_index: int
    score: float  # similaridade de cosseno devolvida pelo Qdrant (maior = melhor)


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    client: QdrantClient | None = None,
    embeddings=None,
    collection_name: str = COLLECTION_NAME,
) -> list[RetrievedChunk]:
    """Busca os `top_k` chunks mais próximos da `query` por similaridade vetorial.

    `embeddings` só precisa expor `embed_query(str) -> list[float]` (interface
    do LangChain) — aceita o objeto real ou um falso no teste.
    """
    from core.embeddings import get_embeddings

    client = client or get_qdrant_client()
    embeddings = embeddings or get_embeddings()

    vetor = embeddings.embed_query(query)
    resposta = client.query_points(
        collection_name=collection_name,
        query=vetor,
        limit=top_k,
        with_payload=True,
    )

    resultados = [
        RetrievedChunk(
            tech=p.payload["tech"],
            url=p.payload["url"],
            text=p.payload["text"],
            chunk_index=p.payload["chunk_index"],
            score=p.score,
        )
        for p in resposta.points
    ]
    logger.info("retrieve: '{}' -> {} chunks", query, len(resultados))
    return resultados


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Monta o bloco de contexto com CITAÇÃO para entregar a um LLM depois.

    Cada trecho vem rotulado com [tech](url), de modo que o agente que consome
    isto possa citar a fonte — requisito do RAG NVIDIA (citações).
    """
    blocos = [
        f"[{c.tech}]({c.url})\n{c.text}"
        for c in chunks
    ]
    return "\n\n---\n\n".join(blocos)


if __name__ == "__main__":
    # Execução manual — exige Qdrant indexado (rode `python -m rag.index` antes)
    # e OPENAI_API_KEY no .env (gera o embedding da query).
    import sys

    pergunta = " ".join(sys.argv[1:]) or "como acelerar inferência de LLM em produção?"
    print(f"Pergunta: {pergunta}\n")
    for i, chunk in enumerate(retrieve(pergunta), 1):
        print(f"#{i}  score={chunk.score:.4f}  [{chunk.tech}]")
        print(f"    {chunk.text[:160].strip()}...")
        print(f"    fonte: {chunk.url}\n")
