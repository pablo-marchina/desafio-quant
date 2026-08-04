"""Fase 2 – Vetorização e ingestão no Qdrant.

Lê chunks de startups_content (PostgreSQL), gera embeddings com
sentence-transformers/all-MiniLM-L6-v2 e armazena em Qdrant com
metadados completos para busca semântica na Fase 3 (LangGraph).

Uso:
  python phase2_vectorizer.py --dry-run          # conta pendentes
  python phase2_vectorizer.py --limit 10         # teste rápido
  python phase2_vectorizer.py --filter-ai        # só AI-signals
  python phase2_vectorizer.py --batch-size 64    # rodada completa
"""
from __future__ import annotations

import argparse
import asyncio
import uuid

import asyncpg
import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from src.config import get_settings
from src.logging_conf import get_logger

logger = get_logger("phase2.vectorizer")

COLLECTION = "startup_chunks"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2


# =============================================================================
# Qdrant helpers
# =============================================================================

async def ensure_collection(client: AsyncQdrantClient) -> None:
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION in existing:
        logger.info("Colecao '%s' ja existe.", COLLECTION)
        return

    await client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    await client.create_payload_index(
        collection_name=COLLECTION,
        field_name="has_ai_signals",
        field_schema=PayloadSchemaType.BOOL,
    )
    await client.create_payload_index(
        collection_name=COLLECTION,
        field_name="startup_id",
        field_schema=PayloadSchemaType.INTEGER,
    )
    logger.info("Colecao '%s' criada com indexes em has_ai_signals e startup_id.", COLLECTION)


def _make_point(row: dict, embedding) -> PointStruct:
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{row['startup_id']}_{row['id']}"))
    return PointStruct(
        id=point_id,
        vector=embedding.tolist(),
        payload={
            "startup_id": row["startup_id"],
            "startup_name": row["startup_name"],
            "chunk_type": row["chunk_type"],
            "has_ai_signals": bool(row["has_ai_signals"]),
            "source_url": row["source_url"] or "",
            "text": row["content"],
        },
    )


# =============================================================================
# PostgreSQL helpers
# =============================================================================

async def _migrate_db(pool: asyncpg.Pool) -> None:
    await pool.execute(
        "ALTER TABLE startups_content ADD COLUMN IF NOT EXISTS is_embedded BOOLEAN DEFAULT FALSE"
    )
    logger.info("Migracao: coluna is_embedded garantida.")


async def _count_pending(pool: asyncpg.Pool, filter_ai: bool) -> int:
    q = "SELECT COUNT(*) FROM startups_content WHERE is_embedded = FALSE"
    if filter_ai:
        q += " AND has_ai_signals = TRUE"
    return await pool.fetchval(q)


async def _fetch_batch(pool: asyncpg.Pool, batch_size: int, filter_ai: bool) -> list[dict]:
    q = """
        SELECT sc.id, sc.startup_id, sc.content, sc.chunk_type,
               sc.has_ai_signals, sc.source_url, sd.name AS startup_name
        FROM startups_content sc
        JOIN startups_discovered sd ON sd.id = sc.startup_id
        WHERE sc.is_embedded = FALSE
    """
    if filter_ai:
        q += " AND sc.has_ai_signals = TRUE"
    q += f" ORDER BY sc.id LIMIT {batch_size}"
    rows = await pool.fetch(q)
    return [dict(r) for r in rows]


# =============================================================================
# CLI
# =============================================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vetoriza chunks do PostgreSQL e ingere no Qdrant.")
    p.add_argument("--dry-run", action="store_true", help="Exibe contagem pendente sem escrever.")
    p.add_argument("--batch-size", type=int, default=None, help="Chunks por lote (padrão: EMBED_BATCH_SIZE).")
    p.add_argument("--limit", type=int, default=None, help="Processa no máximo N chunks (teste).")
    p.add_argument("--filter-ai", action="store_true", help="Processa apenas chunks com has_ai_signals=TRUE.")
    return p.parse_args()


# =============================================================================
# Main
# =============================================================================

async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    batch_size = args.batch_size or settings.embed_batch_size

    # Modelo carregado uma única vez
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Carregando modelo '%s' em device='%s'...", settings.sbert_model, device)
    model = SentenceTransformer(settings.sbert_model, device=device)
    logger.info("Modelo carregado.")

    pool: asyncpg.Pool = await asyncpg.create_pool(
        settings.database_url, min_size=2, max_size=5
    )
    await _migrate_db(pool)

    pending = await _count_pending(pool, args.filter_ai)
    ai_note = " (apenas AI-signals)" if args.filter_ai else ""
    print(f"🔍 Encontrados {pending} chunks pendentes para vetorização{ai_note}.")

    if args.dry_run:
        await pool.close()
        return

    qdrant = AsyncQdrantClient(
        host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False
    )
    await ensure_collection(qdrant)

    sem = asyncio.Semaphore(5)
    total = 0
    batch_num = 0

    try:
        while True:
            remaining = (args.limit - total) if args.limit else batch_size
            effective = min(batch_size, remaining)

            batch = await _fetch_batch(pool, effective, args.filter_ai)
            if not batch:
                break

            batch_num += 1
            texts = [r["content"] for r in batch]
            first_id = batch[0]["id"]
            last_id = batch[-1]["id"]
            print(f"🔄 Processando lote {batch_num} ({len(batch)} chunks, IDs {first_id}–{last_id})...")

            embeddings = await asyncio.to_thread(
                model.encode,
                texts,
                convert_to_tensor=False,
                show_progress_bar=False,
            )

            points = [_make_point(r, emb) for r, emb in zip(batch, embeddings)]

            try:
                async with sem:
                    await qdrant.upsert(collection_name=COLLECTION, points=points, wait=True)
            except Exception as exc:
                logger.error("Falha no upsert do lote %d: %s — lote ignorado.", batch_num, exc)
                continue

            ids = [r["id"] for r in batch]
            await pool.execute(
                "UPDATE startups_content SET is_embedded = TRUE WHERE id = ANY($1)", ids
            )

            total += len(batch)
            print(f"✅ Lote {batch_num} inserido no Qdrant. Acumulados: {total} chunks.")

            if args.limit and total >= args.limit:
                break
    finally:
        await pool.close()
        await qdrant.close()

    print(f"🎉 Vetorização concluída! Total processados: {total}.")


if __name__ == "__main__":
    asyncio.run(main())
