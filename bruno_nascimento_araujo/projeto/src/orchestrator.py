"""Orquestrador central da Fase 1.

Fluxo:
  1. (opcional) migrate()
  2. Fase direta: roda os 5 conectores em paralelo (gather), faz upsert.
  3. Fase aberta: expande grafo de links das sementes, pontua com QFirst, upsert.
  4. Sumario.

Modo --dry-run nao toca o banco: imprime os registros normalizados (util para
validar conectores sem PostgreSQL).
"""
from __future__ import annotations

import asyncio

from .config import Settings, get_settings
from .connectors import ALL_CONNECTORS
from .db import Database
from .enrichment.search_provider import LinkExpansionProvider
from .enrichment.semantic import QFirstScorer
from .http_client import PoliteFetcher, make_client
from .logging_conf import get_logger
from .models import StartupRecord

logger = get_logger("orchestrator")

OPEN_SEARCH_SOURCE = "QFirst Open Search"


class Pipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def run(self, dry_run: bool = False, open_search: bool = True) -> None:
        db: Database | None = None
        if not dry_run:
            db = Database(self.settings)
            await db.connect()
            await db.migrate()

        client = make_client(self.settings)
        try:
            fetcher = PoliteFetcher(client, self.settings)

            direct_records = await self._run_connectors(fetcher)
            await self._persist(db, direct_records, dry_run, "fase direta")

            if open_search:
                open_records = await self._run_open_search(fetcher, db, dry_run)
                await self._persist(db, open_records, dry_run, "busca aberta")
        finally:
            await client.aclose()
            if db is not None:
                await self._print_summary(db)
                await db.close()

    async def _run_connectors(self, fetcher: PoliteFetcher) -> list[StartupRecord]:
        connectors = [cls(fetcher) for cls in ALL_CONNECTORS]
        results = await asyncio.gather(
            *(c.run() for c in connectors), return_exceptions=True
        )
        records: list[StartupRecord] = []
        for connector, res in zip(connectors, results):
            if isinstance(res, Exception):
                logger.error("Conector %s falhou: %s", connector.source_name, res)
                continue
            records.extend(res)
        logger.info("Fase direta: %d registros agregados.", len(records))
        return records

    async def _run_open_search(
        self, fetcher: PoliteFetcher, db: Database | None, dry_run: bool
    ) -> list[StartupRecord]:
        # Sementes: do banco (modo normal) ou dos proprios conectores nao temos
        # acesso aqui em dry-run -> sem DB nao ha sementes persistidas.
        if dry_run or db is None:
            logger.info("Busca aberta requer banco com sementes; pulando em dry-run.")
            return []

        seeds = await db.fetch_seed_websites()
        provider = LinkExpansionProvider(fetcher, self.settings)
        candidates = await provider.discover(seeds)
        if not candidates:
            return []

        scorer = QFirstScorer(self.settings)
        records: list[StartupRecord] = []
        high = 0
        for cand in candidates:
            status, score = scorer.status_for(cand.text_for_scoring())
            if status == "high_priority":
                high += 1
            records.append(
                StartupRecord(
                    name=cand.title,
                    sector="(descoberta - QFirst)",
                    official_website=cand.url,
                    source_name=OPEN_SEARCH_SOURCE,
                    source_url=cand.source_url,
                    status=status,
                )
            )
        logger.info(
            "QFirst (%s): %d candidatos, %d marcados high_priority.",
            scorer.backend, len(records), high,
        )
        return records

    async def _persist(
        self, db: Database | None, records: list[StartupRecord], dry_run: bool, label: str
    ) -> None:
        valid = [r for r in records if r.is_valid()]
        if dry_run or db is None:
            logger.info("[DRY-RUN] %s: %d registros (nao persistidos).", label, len(valid))
            for r in valid[:50]:
                print(
                    f"  - {r.name!r:45} | {r.status:16} | "
                    f"{r.official_website or '-'} | {r.source_name}"
                )
            if len(valid) > 50:
                print(f"  ... (+{len(valid) - 50} registros)")
            return
        n = await db.upsert_many(valid)
        logger.info("%s: %d registros persistidos (upsert).", label, n)

    async def _print_summary(self, db: Database) -> None:
        rows = await db.summary()
        logger.info("===== Sumario startups_discovered =====")
        for row in rows:
            logger.info(
                "  %-28s %-16s -> %d", row["source_name"], row["status"], row["total"]
            )
