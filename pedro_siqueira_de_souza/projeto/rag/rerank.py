"""Reranking dos trechos recuperados (RAG — Entregável 3, commit 4).

Por que rerankar? O retrieval vetorial (rag/retrieve.py) é RÁPIDO mas GROSSEIRO:
compara o vetor da pergunta com os vetores dos chunks: um por um, sem "ler" os
dois juntos. Um *cross-encoder* de reranking (Cohere) recebe a pergunta E cada
trecho ao mesmo tempo e devolve uma relevância muito mais fina. O padrão clássico
de RAG é: recuperar MUITOS candidatos por vetor (barato) e rerankar para POUCOS
(caro, mas só sobre o shortlist).

Fluxo: query --[retrieve fetch_k]--> N candidatos --[Cohere rerank]--> top_n.

Decisões de design:
  - Client INJETÁVEL (igual a embeddings/Qdrant): produção usa o Cohere real;
    testes usam um fake determinístico — sem rede, sem chave.
  - Guardamos os DOIS scores (vetorial original + rerank) no resultado, para a
    comparação antes/depois que o projeto pede no Entregável 3.
  - `rerank-v3.5`: modelo multilíngue da Cohere (as queries podem vir em PT e a
    base está em EN — o cross-encoder multilíngue lida com isso).
"""
from loguru import logger
from pydantic import BaseModel

from core.config import settings
from rag.retrieve import RetrievedChunk, retrieve

DEFAULT_RERANK_MODEL = "rerank-v3.5"
DEFAULT_FETCH_K = 20  # candidatos recuperados por vetor antes do rerank
DEFAULT_TOP_N = 5     # quantos sobram depois do rerank


class RerankedChunk(BaseModel):
    """Chunk reordenado pelo Cohere, com os DOIS scores para comparação."""

    tech: str
    url: str
    text: str
    chunk_index: int
    vector_score: float  # similaridade vetorial original (do retrieve)
    rerank_score: float  # relevância do cross-encoder Cohere (0..1, maior=melhor)


def get_cohere_client():
    """Cliente Cohere V2. Falha cedo e claro se a chave faltar."""
    if not settings.cohere_api_key:
        raise RuntimeError(
            "Reranking exige COHERE_API_KEY, mas está vazio. Preencha no .env."
        )
    import cohere

    return cohere.ClientV2(api_key=settings.cohere_api_key)


def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_n: int = DEFAULT_TOP_N,
    client=None,
    model: str = DEFAULT_RERANK_MODEL,
) -> list[RerankedChunk]:
    """Reordena `chunks` pela relevância à `query` segundo o Cohere.

    `client` só precisa expor `.rerank(model, query, documents, top_n)` devolvendo
    `.results` com `.index` e `.relevance_score` — aceita o real ou um falso.
    """
    if not chunks:
        return []

    client = client or get_cohere_client()
    documentos = [c.text for c in chunks]
    resposta = client.rerank(
        model=model,
        query=query,
        documents=documentos,
        top_n=min(top_n, len(documentos)),
    )

    reordenados = [
        RerankedChunk(
            **chunks[r.index].model_dump(exclude={"score"}),
            vector_score=chunks[r.index].score,
            rerank_score=r.relevance_score,
        )
        for r in resposta.results
    ]
    logger.info("rerank: {} candidatos -> {} reordenados", len(chunks), len(reordenados))
    return reordenados


def _fallback_sem_rerank(
    candidatos: list[RetrievedChunk], top_n: int
) -> list[RerankedChunk]:
    """Degradação graciosa quando o rerank está indisponível (ex.: rate limit
    da chave Trial do Cohere, 429). O reranking é um REFINAMENTO; sem ele,
    devolvemos os `top_n` melhores por similaridade vetorial — pior que o
    cross-encoder, mas muito melhor que perder a startup. O `rerank_score` vira
    o próprio score vetorial (proxy), para o restante do pipeline seguir igual.
    """
    ordenados = sorted(candidatos, key=lambda c: c.score, reverse=True)[:top_n]
    return [
        RerankedChunk(
            **c.model_dump(exclude={"score"}),
            vector_score=c.score,
            rerank_score=c.score,
        )
        for c in ordenados
    ]


def retrieve_and_rerank(
    query: str,
    fetch_k: int = DEFAULT_FETCH_K,
    top_n: int = DEFAULT_TOP_N,
    qdrant_client=None,
    embeddings=None,
    cohere_client=None,
    collection_name: str | None = None,
) -> list[RerankedChunk]:
    """Pipeline completo do RAG: recupera `fetch_k` por vetor e rerankeia p/ `top_n`.

    Se o rerank falhar (rate limit/instabilidade do Cohere), DEGRADA para o
    retrieval vetorial puro em vez de propagar o erro — o RAG não pode parar por
    causa do reranker (tratamento de erro explícito).
    """
    kwargs = {"client": qdrant_client, "embeddings": embeddings}
    if collection_name is not None:
        kwargs["collection_name"] = collection_name
    candidatos = retrieve(query, top_k=fetch_k, **kwargs)
    try:
        return rerank(query, candidatos, top_n=top_n, client=cohere_client)
    except Exception as e:  # 429, rede, etc. — não pode derrubar o RAG
        logger.warning(
            "rerank indisponível ({}); degradando para retrieval vetorial puro",
            type(e).__name__,
        )
        return _fallback_sem_rerank(candidatos, top_n)


if __name__ == "__main__":
    # Comparação ANTES (só vetor) x DEPOIS (rerank) — o ponto do Entregável 3.
    # Exige Qdrant indexado + OPENAI_API_KEY + COHERE_API_KEY no .env.
    import sys

    pergunta = " ".join(sys.argv[1:]) or "como acelerar inferência de LLM em produção?"
    print(f"Pergunta: {pergunta}\n")

    baseline = retrieve(pergunta, top_k=DEFAULT_TOP_N)
    print("=== ANTES (retrieval vetorial puro) ===")
    for i, c in enumerate(baseline, 1):
        print(f"#{i}  vetor={c.score:.4f}  [{c.tech}]  {c.text[:70].strip()}...")

    reranked = retrieve_and_rerank(pergunta, top_n=DEFAULT_TOP_N)
    print("\n=== DEPOIS (com Cohere Rerank) ===")
    for i, c in enumerate(reranked, 1):
        print(f"#{i}  rerank={c.rerank_score:.4f}  (vetor={c.vector_score:.4f})  "
              f"[{c.tech}]  {c.text[:70].strip()}...")
