"""Fase 3 — Recommendation Agent (entrypoint CLI).

Uso:
  python recommend_startup.py --startup-id 1 --dry-run
  python recommend_startup.py --startup-id 1
  python recommend_startup.py --batch-size 10
  python recommend_startup.py --startup-id 1 --reprocess
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import asyncpg
from qdrant_client import AsyncQdrantClient

from src.config import get_settings
from src.logging_conf import get_logger, setup_logging
from src.agents.recommendation_agent import generate_recommendations

setup_logging()
logger = get_logger("recommend.cli")

_SQL_MIGRATION = (Path(__file__).parent / "sql" / "005_recommendations.sql").read_text()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gera recomendações técnicas NVIDIA priorizadas para startups.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--startup-id", type=int, metavar="N", help="Gera recomendações para a startup com ID N.")
    group.add_argument("--batch-size", type=int, metavar="N", help="Gera recomendações para as N primeiras startups classificadas sem recomendação.")
    p.add_argument("--dry-run", action="store_true", help="Exibe as recomendações no console sem salvar.")
    p.add_argument("--reprocess", action="store_true", help="Força a regeração mesmo se já existir recomendação.")
    return p.parse_args()


async def _run_single(startup_id: int, pool: asyncpg.Pool, qdrant: AsyncQdrantClient, dry_run: bool, reprocess: bool) -> None:
    if not reprocess and not dry_run:
        existing = await pool.fetchval("SELECT id FROM recommendations WHERE startup_id = $1", startup_id)
        if existing:
            logger.info("Startup %d já possui recomendação. Use --reprocess para regenerar.", startup_id)
            return
    try:
        result = await generate_recommendations(startup_id, pool, qdrant, dry_run=dry_run)
    except ValueError as exc:
        logger.error("Startup %d: %s", startup_id, exc)
        return
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Startup {startup_id} ({result.startup_name}): "
          f"{len(result.recommendations)} recomendações via {result.provider_used}")
    for r in result.recommendations:
        print(f"  [{r.priority.upper()}] {r.tech_name} ({r.category}) — evidências: {r.evidence_chunks}")


async def _run_batch(batch_size: int, pool: asyncpg.Pool, qdrant: AsyncQdrantClient, dry_run: bool, reprocess: bool) -> None:
    if reprocess:
        rows = await pool.fetch("SELECT startup_id FROM classifications ORDER BY startup_id LIMIT $1", batch_size)
    else:
        rows = await pool.fetch(
            """
            SELECT c.startup_id FROM classifications c
            LEFT JOIN recommendations r ON r.startup_id = c.startup_id
            WHERE r.startup_id IS NULL
            ORDER BY c.startup_id LIMIT $1
            """,
            batch_size,
        )
    ids = [r["startup_id"] for r in rows]
    if not ids:
        print("Nenhuma startup classificada pendente de recomendação.")
        return

    print(f"📋 Gerando recomendações para {len(ids)} startups (até 5 simultâneas)...")
    sem = asyncio.Semaphore(5)

    async def _bounded(sid: int) -> None:
        async with sem:
            try:
                await _run_single(sid, pool, qdrant, dry_run, reprocess=True)
            except Exception as exc:
                logger.error("Startup %d falhou: %s", sid, exc)

    await asyncio.gather(*[_bounded(sid) for sid in ids])
    print(f"\n✅ Batch concluído. {len(ids)} startups processadas.")


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    pool: asyncpg.Pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=5)
    await pool.execute(_SQL_MIGRATION)
    qdrant = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False)
    try:
        if args.startup_id:
            await _run_single(args.startup_id, pool, qdrant, args.dry_run, args.reprocess)
        else:
            await _run_batch(args.batch_size, pool, qdrant, args.dry_run, args.reprocess)
    finally:
        await pool.close()
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(main())
