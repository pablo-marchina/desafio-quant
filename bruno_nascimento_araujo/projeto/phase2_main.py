"""Entrypoint da Fase 2 - Deep Extraction.

Exemplos:
  python phase2_main.py --migrate
  python phase2_main.py --dry-run
  python phase2_main.py --batch-size 20
  python phase2_main.py --status high_priority
  python phase2_main.py --status pending          # pending_deep_scan + missing_url
  python phase2_main.py --status missing_url
  python phase2_main.py --status pending_deep_scan missing_url   # multiplos
  python phase2_main.py --status high_priority --batch-size 10
"""
from __future__ import annotations

import argparse
import asyncio

from src.config import get_settings
from src.db import Database
from src.logging_conf import get_logger, setup_logging
from src.phase2.orchestrator import DeepScanOrchestrator


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NVIDIA Startup AI Radar - Fase 2 (Deep Extraction)")
    p.add_argument("--migrate", action="store_true", help="Aplica migracoes SQL (incluindo 002_content.sql) e sai.")
    p.add_argument("--dry-run", action="store_true", help="Extrai sem persistir no banco. Exibe ExtractedStartupData.")
    p.add_argument("--batch-size", type=int, default=None, help="Tamanho do lote (padrao: DEEP_SCAN_BATCH_SIZE do .env).")
    p.add_argument(
        "--status",
        nargs="+",
        choices=["pending_deep_scan", "high_priority", "missing_url", "all", "pending"],
        default=["all"],
        metavar="STATUS",
        help=(
            "Um ou mais status a processar. "
            "'all' = pending_deep_scan + high_priority. "
            "'pending' = pending_deep_scan + missing_url. "
            "Exemplos: --status missing_url pending_deep_scan"
        ),
    )
    return p.parse_args()


_STATUS_ALIASES: dict[str, list[str]] = {
    "all": ["pending_deep_scan", "high_priority"],
    "pending": ["pending_deep_scan", "missing_url"],
}


def _resolve_statuses(raw: list[str]) -> list[str]:
    """Expande aliases e deduplica a lista de status."""
    resolved: list[str] = []
    for s in raw:
        resolved.extend(_STATUS_ALIASES.get(s, [s]))
    return list(dict.fromkeys(resolved))  # preserva ordem, remove duplicatas


async def _migrate_only() -> None:
    db = Database()
    await db.connect()
    await db.migrate()
    await db.close()


async def _main() -> None:
    args = parse_args()
    settings = get_settings()
    setup_logging(settings.log_level)
    log = get_logger("phase2.main")

    if args.migrate:
        log.info("Aplicando migracoes SQL (Fase 2).")
        await _migrate_only()
        return

    statuses = _resolve_statuses(args.status)
    log.info(
        "Fase 2: dry_run=%s | status=%s | batch_size=%s",
        args.dry_run, statuses, args.batch_size or "padrao do .env",
    )

    orchestrator = DeepScanOrchestrator(settings)
    await orchestrator.run(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        statuses=statuses,
    )
    log.info("Fase 2 concluida.")


if __name__ == "__main__":
    asyncio.run(_main())
