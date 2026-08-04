"""Fase 3 — Briefing Agent (entrypoint CLI).

Uso:
  python brief_startup.py --startup-id 1 --dry-run
  python brief_startup.py --startup-id 1
  python brief_startup.py --startup-id 1 --export-file
  python brief_startup.py --batch-size 10
  python brief_startup.py --startup-id 1 --reprocess
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import asyncpg
from qdrant_client import AsyncQdrantClient

from src.config import get_settings
from src.logging_conf import get_logger, setup_logging
from src.agents.briefing_agent import generate_briefing

setup_logging()
logger = get_logger("brief.cli")

_SQL_MIGRATION = (Path(__file__).parent / "sql" / "006_briefings.sql").read_text()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gera briefings executivos (Markdown) para startups.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--startup-id", type=int, metavar="N", help="Gera briefing para a startup com ID N.")
    group.add_argument("--batch-size", type=int, metavar="N", help="Gera briefings para as N primeiras startups classificadas+recomendadas sem briefing.")
    p.add_argument("--dry-run", action="store_true", help="Exibe o Markdown no console sem salvar nada.")
    p.add_argument("--export-file", action="store_true", help="Salva o Markdown em reports/{id}_{nome}.md.")
    p.add_argument("--reprocess", action="store_true", help="Força a regeração mesmo se já existir briefing.")
    return p.parse_args()


async def _run_single(startup_id: int, pool: asyncpg.Pool, qdrant: AsyncQdrantClient, dry_run: bool, export_file: bool, reprocess: bool) -> None:
    if not reprocess and not dry_run:
        existing = await pool.fetchval("SELECT id FROM briefings WHERE startup_id = $1", startup_id)
        if existing:
            logger.info("Startup %d já possui briefing. Use --reprocess para regenerar.", startup_id)
            return
    try:
        result = await generate_briefing(startup_id, pool, qdrant, dry_run=dry_run, export_file=export_file)
    except ValueError as exc:
        logger.error("Startup %d: %s", startup_id, exc)
        return
    if not dry_run:
        print(f"Startup {startup_id} ({result.startup_name}): briefing gerado ({len(result.report_markdown)} caracteres).")


async def _run_batch(batch_size: int, pool: asyncpg.Pool, qdrant: AsyncQdrantClient, dry_run: bool, export_file: bool, reprocess: bool) -> None:
    if reprocess:
        rows = await pool.fetch(
            """
            SELECT c.startup_id FROM classifications c
            JOIN recommendations r ON r.startup_id = c.startup_id
            ORDER BY c.startup_id LIMIT $1
            """,
            batch_size,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT c.startup_id FROM classifications c
            JOIN recommendations r ON r.startup_id = c.startup_id
            LEFT JOIN briefings b ON b.startup_id = c.startup_id
            WHERE b.startup_id IS NULL
            ORDER BY c.startup_id LIMIT $1
            """,
            batch_size,
        )
    ids = [r["startup_id"] for r in rows]
    if not ids:
        print("Nenhuma startup classificada+recomendada pendente de briefing.")
        return

    print(f"📋 Gerando briefings para {len(ids)} startups (até 5 simultâneas)...")
    sem = asyncio.Semaphore(5)

    async def _bounded(sid: int) -> None:
        async with sem:
            try:
                await _run_single(sid, pool, qdrant, dry_run, export_file, reprocess=True)
            except Exception as exc:
                logger.error("Startup %d falhou: %s", sid, exc)

    await asyncio.gather(*[_bounded(sid) for sid in ids], return_exceptions=True)
    print(f"\n✅ Batch concluído. {len(ids)} startups processadas.")


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    pool: asyncpg.Pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=5)
    await pool.execute(_SQL_MIGRATION)
    qdrant = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False)
    try:
        if args.startup_id:
            await _run_single(args.startup_id, pool, qdrant, args.dry_run, args.export_file, args.reprocess)
        else:
            await _run_batch(args.batch_size, pool, qdrant, args.dry_run, args.export_file, args.reprocess)
    finally:
        await pool.close()
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(main())
