"""Modulo 4 - Orquestrador de ingestao profunda (Fase 2).

Fluxo por startup:
  1. Verifica robots.txt (skip se bloqueado)
  2. Descobre URL se ausente via discover_startup_url (4 niveis de failover)
  3. Extrai conteudo rico via extract_startup_data (3 niveis)
  4. Divide em chunks e insere na tabela startups_content
  5. Atualiza status: deep_scan_completed | deep_scan_failed | missing_url

Controle de concorrencia: asyncio.Semaphore(deep_scan_concurrency).
Retry em erros transitorios: tenacity com backoff exponencial.

Criterio de high_priority (auditoria):
  Os registros com status high_priority foram definidos na Fase 1 atendendo a
  PELO MENOS UM dos seguintes criterios:
    1. Setor em ('Inteligencia Artificial', 'Deep Tech', 'Machine Learning', 'IA')
    2. Aparece em 2+ fontes distintas no banco (indicador de relevancia cruzada)
    3. Score QFirst >= QFIRST_THRESHOLD (gravado na Fase 1)
    4. Funding > R$10M se disponivel nos metadados (enriquecido pela Fase 2)
  Quando --status high_priority e passado, o batch prioriza esses alvos de maior
  valor antes de processar os pending_deep_scan genericos.
"""
from __future__ import annotations

import asyncio

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import httpx

from ..config import Settings, get_settings
from ..db import Database
from ..http_client import PoliteFetcher, make_deep_client
from ..logging_conf import get_logger
from ..models import normalize_url
from .chunker import ChunkProcessor
from .robots import RobotsChecker
from .tools.extractor import ExtractedStartupData, extract_startup_data
from .tools.url_discovery import discover_startup_url

logger = get_logger("phase2.orchestrator")

_RETRYABLE_HTTP = (httpx.TransportError, httpx.HTTPStatusError)


class DeepScanOrchestrator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._db = Database(self.settings)
        self._robots = RobotsChecker()
        self._chunker = ChunkProcessor(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        self._sem = asyncio.Semaphore(self.settings.deep_scan_concurrency)

    async def run(
        self,
        batch_size: int | None = None,
        dry_run: bool = False,
        statuses: list[str] | None = None,
    ) -> None:
        batch_size = batch_size or self.settings.deep_scan_batch_size
        statuses = statuses or ["pending_deep_scan", "high_priority"]

        if not dry_run:
            await self._db.connect()
            await self._db.migrate()

        client = make_deep_client()
        try:
            fetcher = PoliteFetcher(client, self.settings)
            processed = 0
            while True:
                if dry_run:
                    # Dry-run: usa URLs estaticas de exemplo para demo
                    batch = [
                        {"id": 0, "name": "Acme AI", "official_website": "https://example.com", "sector": "IA"}
                    ][:batch_size]
                    if processed > 0:
                        break
                else:
                    batch = await self._db.fetch_pending_deep_scan(batch_size, statuses)
                    if not batch:
                        logger.info("Nenhum registro pendente. Pipeline concluido.")
                        break

                logger.info("Processando lote de %d startups...", len(batch))
                tasks = [self._process_one(row, fetcher, dry_run) for row in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                ok = sum(1 for r in results if r is True)
                fail = sum(1 for r in results if r is not True)
                logger.info("Lote: %d ok, %d falhas.", ok, fail)
                processed += len(batch)

                if dry_run:
                    break
        finally:
            await client.aclose()
            if not dry_run:
                await self._print_summary()
                await self._db.close()

    # Timeout maximo por startup. Cobre o pior caso: crawl4ai com Playwright
    # em SPA que nunca termina de renderizar.
    _PER_STARTUP_TIMEOUT = 120  # segundos

    async def _process_one(self, row, fetcher: PoliteFetcher, dry_run: bool) -> bool:
        startup_id: int = row["id"]
        name: str = row["name"]
        url: str | None = normalize_url(row.get("official_website"))
        sector: str = row.get("sector") or ""

        async with self._sem:
            try:
                return await asyncio.wait_for(
                    self._process_one_inner(startup_id, name, url, sector, fetcher, dry_run),
                    timeout=self._PER_STARTUP_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "[%s] Timeout de %ds atingido — marcando deep_scan_failed.",
                    name, self._PER_STARTUP_TIMEOUT,
                )
                if not dry_run:
                    try:
                        await self._db.update_startup_status(startup_id, "deep_scan_failed")
                    except Exception as db_exc:
                        logger.error("[%s] Falhou ao gravar timeout como deep_scan_failed: %s", name, db_exc)
                return False

    async def _process_one_inner(
        self, startup_id: int, name: str, url: str | None, sector: str,
        fetcher: PoliteFetcher, dry_run: bool,
    ) -> bool:
        try:
            # 1. Descoberta de URL se ausente
            if not url:
                logger.info("[%s] URL ausente — iniciando URL Discovery.", name)
                url = await self._discover_url(name, sector, startup_id, dry_run)
                if not url:
                    return True  # status ja atualizado para missing_url

            # 2. Verificacao de robots.txt
            if not await self._robots.is_allowed(url, fetcher):
                logger.warning("[%s] robots.txt bloqueia %s — marcando deep_scan_failed.", name, url)
                if not dry_run:
                    await self._db.update_startup_status(startup_id, "deep_scan_failed")
                return False

            # 3. Extracao profunda com retry
            logger.info("[%s] Extraindo %s...", name, url)
            data = await self._extract_with_retry(url)
            logger.info(
                "[%s] Nivel: %s | ai_score: %.2f | chunks esperados: via chunker.",
                name, data.extraction_level, data.ai_signal_score,
            )

            # 4. Chunking e insercao
            chunks = self._chunker.process(data, startup_id)
            if dry_run:
                logger.info("[DRY-RUN] %s: %d chunks (nao inseridos).", name, len(chunks))
                print(f"\n--- {name} ---")
                print(f"  url: {url}")
                print(f"  nivel: {data.extraction_level}")
                print(f"  core_business: {(data.core_business or '')[:120]!r}...")
                print(f"  use_cases: {data.use_cases[:3]}")
                print(f"  tech_stack: {data.tech_stack_raw[:5]}")
                print(f"  ai_signal_score: {data.ai_signal_score:.2f}")
                print(f"  chunks: {len(chunks)}")
                return True

            inserted = await self._db.insert_chunks(chunks)
            logger.info("[%s] %d chunks inseridos.", name, inserted)

            # 5. Atualiza status para deep_scan_completed
            await self._db.update_startup_status(startup_id, "deep_scan_completed")
            return True

        except Exception as exc:
            logger.error("[%s] Falha nao recuperavel: %s", name, exc, exc_info=True)
            if not dry_run:
                try:
                    await self._db.update_startup_status(startup_id, "deep_scan_failed")
                except Exception as db_exc:
                    # Se o update de status tambem falhar, o registro permanece
                    # pending e seria re-buscado. Logamos mas nunca propagamos.
                    logger.error(
                        "[%s] Falhou ao gravar deep_scan_failed (startup permanece pending): %s",
                        name, db_exc,
                    )
            return False

    async def _discover_url(
        self, name: str, sector: str, startup_id: int, dry_run: bool
    ) -> str | None:
        try:
            # Invoca como LangGraph tool (ainvoke) ou funcao async pura
            raw = await discover_startup_url.ainvoke({"startup_name": name, "sector": sector})  # type: ignore[union-attr]
        except AttributeError:
            raw = await discover_startup_url(name, sector)  # type: ignore[operator]

        url = normalize_url(raw)
        if not url:
            if not dry_run:
                await self._db.update_startup_status(startup_id, "missing_url")
            return None
        if not dry_run:
            # Persiste a URL descoberta na startup mae
            async with self._db._pool.acquire() as conn:  # type: ignore[union-attr]
                await conn.execute(
                    "UPDATE startups_discovered SET official_website=$1, updated_at=CURRENT_TIMESTAMP WHERE id=$2",
                    url, startup_id,
                )
        return url

    @retry(
        retry=retry_if_exception_type(_RETRYABLE_HTTP),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=30),
        reraise=True,
    )
    async def _extract_with_retry(self, url: str) -> ExtractedStartupData:
        try:
            result = await extract_startup_data.ainvoke({"url": url})  # type: ignore[union-attr]
        except AttributeError:
            result = await extract_startup_data(url)  # type: ignore[operator]
        return ExtractedStartupData(**result)

    async def _print_summary(self) -> None:
        try:
            rows = await self._db.summary()
            logger.info("===== Resumo startups_discovered =====")
            for row in rows:
                logger.info(
                    "  %-28s %-22s -> %d",
                    row["source_name"], row["status"], row["total"],
                )
            content_rows = await self._db._pool.fetch(  # type: ignore[union-attr]
                "SELECT chunk_type, count(*) as n, bool_or(has_ai_signals) as any_ai "
                "FROM startups_content GROUP BY chunk_type ORDER BY chunk_type"
            )
            logger.info("===== Resumo startups_content =====")
            for row in content_rows:
                logger.info("  %-15s -> %d chunks | ai_signal: %s", row["chunk_type"], row["n"], row["any_ai"])
        except Exception as exc:
            logger.warning("Erro ao gerar resumo: %s", exc)
