"""Entrypoint da Fase 1 - Scraper 1 (Discovery).

Exemplos:
  python main.py                          # pipeline completo (conectores + busca aberta)
  python main.py --no-open-search         # so extracao direta + persistencia
  python main.py --dry-run --no-open-search   # testa conectores sem PostgreSQL
  python main.py --migrate                # apenas aplica as migracoes SQL
"""
from __future__ import annotations

import argparse
import asyncio

from src.config import get_settings
from src.db import Database
from src.logging_conf import get_logger, setup_logging
from src.orchestrator import Pipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NVIDIA Startup AI Radar - Fase 1")
    p.add_argument("--migrate", action="store_true", help="Apenas aplica migracoes SQL e sai.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao toca o banco; imprime registros normalizados dos conectores.",
    )
    p.add_argument(
        "--no-open-search",
        action="store_true",
        help="Desativa a fase de busca aberta (QFirst).",
    )
    return p.parse_args()


async def _migrate_only() -> None:
    db = Database()
    await db.connect()
    await db.migrate()
    await db.close()


async def _main() -> None:
    args = parse_args()
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger("main")

    if args.migrate:
        log.info("Executando apenas migracoes.")
        await _migrate_only()
        return

    log.info(
        "Iniciando pipeline (dry_run=%s, open_search=%s).",
        args.dry_run, not args.no_open_search,
    )
    pipeline = Pipeline(settings)
    await pipeline.run(dry_run=args.dry_run, open_search=not args.no_open_search)
    log.info("Pipeline finalizado.")


if __name__ == "__main__":
    asyncio.run(_main())
