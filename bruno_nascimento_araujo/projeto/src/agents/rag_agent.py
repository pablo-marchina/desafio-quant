"""RAG Agent — Fase 3 (Agente 2).

Dado um startup_id ou uma query textual livre, executa:
  1. Query Transformation via LLM (quando startup_id fornecido)
  2. Busca híbrida no Qdrant (vetorial + BM25) com fusão RRF
  3. Reranking com Cohere Rerank v3 (AsyncClientV2)
  4. Cache opcional no PostgreSQL (nvidia_rag_cache)
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import asyncpg
import numpy as np
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
from rank_bm25 import BM25Okapi

from ..config import get_settings
from ..logging_conf import get_logger
from .llm_providers import generate_text_with_fallback

logger = get_logger("agents.rag")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

NVIDIA_COLLECTION = "nvidia_tech_knowledge"
STARTUP_COLLECTION = "startup_chunks"
VECTOR_TOP_K = 60
RRF_K = 60
RRF_TOP = 20

QUERY_TRANSFORM_PROMPT = """\
Você recebe dados de uma startup brasileira. \
Gere UMA frase de busca concisa (máximo 30 palavras) descrevendo quais \
tecnologias NVIDIA (NIM, Triton, RAPIDS, NeMo, cuVS, DOCA, etc.) podem \
resolver os gaps de infraestrutura, latência, dados ou governança desta startup. \
Responda APENAS com a frase, sem pontuação extra, sem aspas, sem markdown.\
"""


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class RAGChunkResult(BaseModel):
    tech_name: str
    category: str
    source_url: str
    text: str
    rerank_score: float


class RAGResult(BaseModel):
    query: str
    condensed_query: str
    top_chunks: list[RAGChunkResult]
    retrieval_time_ms: float
    rerank_time_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# Singleton do modelo de embedding
# ---------------------------------------------------------------------------

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Carregando modelo de embedding all-MiniLM-L6-v2...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


# ---------------------------------------------------------------------------
# Query Transformation
# ---------------------------------------------------------------------------

async def transform_query_with_llm(
    startup_id: int,
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
) -> str:
    """Converte o perfil de uma startup em uma frase de busca curta (≤30 palavras)."""
    row = await pool.fetchrow(
        "SELECT name, sector FROM startups_discovered WHERE id = $1", startup_id
    )
    if not row:
        raise ValueError(f"Startup id={startup_id} não encontrada.")
    name: str = row["name"]
    sector: str = row["sector"] or "tecnologia"

    # Busca chunks com sinal AI primeiro
    results, _ = await qdrant.scroll(
        collection_name=STARTUP_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="startup_id", match=MatchValue(value=startup_id))]
        ),
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    chunks = sorted(
        [{"text": p.payload.get("text", ""), "has_ai": bool(p.payload.get("has_ai_signals", False))}
         for p in results],
        key=lambda c: (0 if c["has_ai"] else 1),
    )[:8]

    chunk_texts = "\n".join(f"- {c['text'][:200]}" for c in chunks) if chunks else "(sem dados)"

    user_prompt = (
        f"Startup: {name}\n"
        f"Setor: {sector}\n"
        f"Trechos relevantes:\n{chunk_texts}"
    )

    condensed, provider = await generate_text_with_fallback(
        QUERY_TRANSFORM_PROMPT, user_prompt, context_label=f"startup_{startup_id}"
    )
    logger.info("Query transformada via %s: %r", provider, condensed)

    # Garante ≤30 palavras
    words = condensed.split()
    if len(words) > 30:
        condensed = " ".join(words[:30])

    return condensed


# ---------------------------------------------------------------------------
# Busca híbrida: Vetorial + BM25 + RRF
# ---------------------------------------------------------------------------

async def hybrid_search(
    query: str,
    qdrant: AsyncQdrantClient,
    category_filter: list[str] | None = None,
) -> tuple[list[dict], float]:
    """Retorna (top20_chunks, retrieval_ms)."""
    t0 = time.monotonic()
    model = _get_embedding_model()
    embedding = await asyncio.to_thread(model.encode, [query])
    query_vector = embedding[0].tolist()

    qdrant_filter: Filter | None = None
    if category_filter:
        qdrant_filter = Filter(
            must=[FieldCondition(key="category", match=MatchAny(any=category_filter))]
        )

    response = await qdrant.query_points(
        collection_name=NVIDIA_COLLECTION,
        query=query_vector,
        limit=VECTOR_TOP_K,
        query_filter=qdrant_filter,
        with_payload=True,
    )
    vector_hits = response.points

    n = len(vector_hits)
    if n == 0:
        return [], (time.monotonic() - t0) * 1000

    texts = [h.payload.get("text", "") for h in vector_hits]

    # BM25 nos mesmos textos recuperados pela busca vetorial
    tokenized = [t.lower().split() for t in texts]
    bm25 = BM25Okapi(tokenized)
    bm25_scores: np.ndarray = bm25.get_scores(query.lower().split())

    # RRF: posição vetorial (0-based) + posição BM25
    bm25_rank_order = np.argsort(-bm25_scores).tolist()
    bm25_rank = {idx: rank for rank, idx in enumerate(bm25_rank_order)}

    rrf: dict[int, float] = {}
    for i in range(n):
        rrf[i] = 1.0 / (RRF_K + i + 1) + 1.0 / (RRF_K + bm25_rank[i] + 1)

    top20_indices = sorted(rrf, key=lambda i: -rrf[i])[:RRF_TOP]
    top20_chunks = [
        {
            "text": texts[i],
            "tech_name": vector_hits[i].payload.get("tech_name", ""),
            "category": vector_hits[i].payload.get("category", ""),
            "source_url": vector_hits[i].payload.get("source_url", ""),
        }
        for i in top20_indices
    ]

    retrieval_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "📚 Busca hibrida: Vetorial (%d) + BM25 (%d) -> RRF (%d) em %.0fms",
        n, n, len(top20_chunks), retrieval_ms,
    )
    return top20_chunks, retrieval_ms


# ---------------------------------------------------------------------------
# Reranking com Cohere
# ---------------------------------------------------------------------------

async def rerank_with_cohere(
    query: str,
    chunks: list[dict],
    top_k: int,
) -> tuple[list[RAGChunkResult], float | None]:
    """Rerankeia chunks com Cohere Rerank v3, com failover entre KEY_1 e KEY_2.

    Retorna (resultados, rerank_ms). Se ambas as chaves falharem (ou nenhuma
    estiver configurada), cai para o fallback RRF (rerank_score=1.0, rerank_ms=None).
    """
    cfg = get_settings()
    keys = [
        (label, key)
        for label, key in (
            ("Cohere KEY_1", cfg.cohere_api_key_1),
            ("Cohere KEY_2", cfg.cohere_api_key_2),
        )
        if key
    ]

    if not keys:
        logger.warning("Nenhuma COHERE_API_KEY configurada — fallback para top-%d do RRF.", top_k)
        return [RAGChunkResult(**c, rerank_score=1.0) for c in chunks[:top_k]], None

    from cohere import AsyncClientV2

    prev_label: str | None = None
    for label, api_key in keys:
        if prev_label:
            logger.warning("Rotacao de chave [%s → %s] para reranking.", prev_label, label)
        try:
            t0 = time.monotonic()
            client = AsyncClientV2(api_key=api_key, timeout=30.0)
            response = await client.rerank(
                model="rerank-multilingual-v3.0",
                query=query,
                documents=[c["text"] for c in chunks],
                top_n=top_k,
            )
            rerank_ms = (time.monotonic() - t0) * 1000
            reranked = [
                RAGChunkResult(
                    **{k: v for k, v in chunks[r.index].items() if k != "rerank_score"},
                    rerank_score=float(r.relevance_score if r.relevance_score is not None else 0.0),
                )
                for r in response.results
            ]
            logger.info(
                "🔁 Reranking de %d chunks com %s em %.0fms -> top %d",
                len(chunks), label, rerank_ms, len(reranked),
            )
            return reranked, rerank_ms
        except Exception as exc:
            status_hint = ""
            msg = str(exc)
            if "429" in msg or "rate" in msg.lower() or "quota" in msg.lower():
                status_hint = " (quota/rate-limit)"
            elif "401" in msg or "403" in msg or "unauthorized" in msg.lower():
                status_hint = " (chave invalida)"
            elif "timeout" in msg.lower() or "connect" in msg.lower():
                status_hint = " (timeout)"
            logger.warning("Falha em %s%s para reranking: %s", label, status_hint, exc)
            prev_label = label

    logger.error("Todas as chaves Cohere falharam — fallback para top-%d do RRF.", top_k)
    return [RAGChunkResult(**c, rerank_score=1.0) for c in chunks[:top_k]], None


# ---------------------------------------------------------------------------
# Cache PostgreSQL
# ---------------------------------------------------------------------------

async def cache_result(
    pool: asyncpg.Pool,
    startup_id: int,
    query: str,
    chunks: list[RAGChunkResult],
) -> None:
    recommendations = json.dumps([c.model_dump() for c in chunks], ensure_ascii=False)
    await pool.execute(
        """
        INSERT INTO nvidia_rag_cache (startup_id, query, recommendations)
        VALUES ($1, $2, $3::jsonb)
        ON CONFLICT DO NOTHING
        """,
        startup_id,
        query,
        recommendations,
    )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

async def run_rag(
    startup_id: int | None,
    query: str | None,
    top_k: int,
    category_filter: list[str] | None,
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    dry_run: bool = False,
) -> RAGResult:
    """Ponto de entrada do RAG Agent."""
    original_query = query or f"startup_{startup_id}"

    if startup_id is not None:
        logger.info("🔍 Buscando tecnologias para startup ID %d...", startup_id)
        condensed = await transform_query_with_llm(startup_id, pool, qdrant)
        print(f"✍️  Query transformada pelo LLM: {condensed}")
    else:
        condensed = query  # type: ignore[assignment]
        print(f"🔎 Query direta: {condensed}")

    top20, retrieval_ms = await hybrid_search(condensed, qdrant, category_filter)

    if not top20:
        logger.warning("Nenhum chunk encontrado na busca hibrida.")
        return RAGResult(
            query=original_query,
            condensed_query=condensed,
            top_chunks=[],
            retrieval_time_ms=retrieval_ms,
        )

    top_chunks, rerank_ms = await rerank_with_cohere(condensed, top20, top_k)

    tech_names = [c.tech_name for c in top_chunks]
    print(f"✅ Top {top_k}: {tech_names}")

    result = RAGResult(
        query=original_query,
        condensed_query=condensed,
        top_chunks=top_chunks,
        retrieval_time_ms=retrieval_ms,
        rerank_time_ms=rerank_ms,
    )

    if not dry_run and startup_id is not None:
        await cache_result(pool, startup_id, condensed, top_chunks)
        logger.info("💾 Resultado armazenado no cache (nvidia_rag_cache).")

    return result
