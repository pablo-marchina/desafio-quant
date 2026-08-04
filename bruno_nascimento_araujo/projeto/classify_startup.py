"""Fase 3 — Startup Classifier Agent (entrypoint CLI).

Uso:
  python classify_startup.py --startup-id 1 --dry-run
  python classify_startup.py --startup-id 1
  python classify_startup.py --batch-size 10
  python classify_startup.py --startup-id 1 --model groq:llama3-8b-8192
  python classify_startup.py --startup-id 1 --reprocess
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import asyncpg
from qdrant_client import AsyncQdrantClient

from src.config import get_settings
from src.logging_conf import get_logger, setup_logging
from src.agents.classifier import classify_startup

setup_logging()
logger = get_logger("classifier.cli")

_SQL_MIGRATION = (Path(__file__).parent / "sql" / "003_classifications.sql").read_text()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Classifica startups como AI-native, AI-enabled ou non-AI.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--startup-id", type=int, metavar="N", help="Classifica a startup com ID N.")
    group.add_argument("--batch-size", type=int, metavar="N", help="Classifica as N primeiras startups sem classificação.")
    p.add_argument("--dry-run",   action="store_true", help="Mostra prompt e resposta LLM sem salvar.")
    p.add_argument("--reprocess", action="store_true", help="Força reclassificação mesmo se já existir.")
    p.add_argument(
        "--model",
        metavar="PROVIDER:MODEL",
        help="Override do provedor (ex: groq:llama3-8b-8192, gemini:gemini-1.5-pro, ollama:llama3.2:3b).",
    )
    return p.parse_args()


async def _run_single(
    startup_id: int,
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    force_provider: str | None,
    dry_run: bool,
    reprocess: bool,
) -> None:
    # Verifica se já classificada (skip sem --reprocess)
    if not reprocess and not dry_run:
        existing = await pool.fetchval(
            "SELECT classification FROM classifications WHERE startup_id = $1", startup_id
        )
        if existing:
            logger.info(
                "Startup %d já classificada como '%s'. Use --reprocess para forçar.",
                startup_id, existing,
            )
            return

    result = await classify_startup(startup_id, pool, qdrant, force_provider, dry_run)
    print(
        f"\n{'[DRY-RUN] ' if dry_run else ''}Startup {startup_id} ({result.startup_name}): "
        f"{result.classification.upper()} | confiança={result.confidence_score:.2f} | provedor={result.provider_used}"
    )
    print(f"  → {result.justification}")


async def _run_batch(
    batch_size: int,
    pool: asyncpg.Pool,
    qdrant: AsyncQdrantClient,
    force_provider: str | None,
    dry_run: bool,
    reprocess: bool,
) -> None:
    # Busca IDs sem classificação (ou todos, se --reprocess)
    if reprocess:
        rows = await pool.fetch(
            "SELECT id FROM startups_discovered ORDER BY id LIMIT $1", batch_size
        )
    else:
        rows = await pool.fetch(
            """
            SELECT sd.id FROM startups_discovered sd
            LEFT JOIN classifications c ON c.startup_id = sd.id
            WHERE c.startup_id IS NULL
            ORDER BY sd.id
            LIMIT $1
            """,
            batch_size,
        )

    ids = [r["id"] for r in rows]
    if not ids:
        print("Nenhuma startup pendente de classificação.")
        return

    print(f"📋 Classificando {len(ids)} startups em paralelo (até 5 simultâneas)...")

    sem = asyncio.Semaphore(5)

    async def _bounded(startup_id: int) -> None:
        async with sem:
            try:
                await _run_single(startup_id, pool, qdrant, force_provider, dry_run, reprocess=True)
            except Exception as exc:
                logger.error("Startup %d falhou: %s", startup_id, exc)

    await asyncio.gather(*[_bounded(sid) for sid in ids], return_exceptions=True)
    print(f"\n✅ Batch concluído. {len(ids)} startups processadas.")


async def main() -> None:
    args = _parse_args()
    settings = get_settings()

    pool: asyncpg.Pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=5)

    # Migração idempotente da tabela classifications
    await pool.execute(_SQL_MIGRATION)

    qdrant = AsyncQdrantClient(
        host=settings.qdrant_host, port=settings.qdrant_port, check_compatibility=False
    )

    try:
        if args.startup_id:
            await _run_single(
                args.startup_id, pool, qdrant,
                force_provider=args.model,
                dry_run=args.dry_run,
                reprocess=args.reprocess,
            )
        else:
            await _run_batch(
                args.batch_size, pool, qdrant,
                force_provider=args.model,
                dry_run=args.dry_run,
                reprocess=args.reprocess,
            )
    finally:
        await pool.close()
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(main())
