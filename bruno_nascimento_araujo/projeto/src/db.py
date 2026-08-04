"""Camada de banco assincrona (asyncpg): pool, migracao e upsert idempotente."""
from __future__ import annotations

from pathlib import Path

import asyncpg

from .config import Settings, get_settings
from .logging_conf import get_logger
from .models import StartupRecord

logger = get_logger("db")

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

# A clausula ON CONFLICT precisa repetir EXATAMENTE a expressao do indice unico
# funcional definido em 001_init.sql (NULL-safe via COALESCE).
_UPSERT_SQL = """
INSERT INTO startups_discovered
    (name, sector, official_website, source_name, source_url, status)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (lower(trim(name)), coalesce(lower(official_website), ''))
DO UPDATE SET
    updated_at  = CURRENT_TIMESTAMP,
    source_name = EXCLUDED.source_name,
    sector      = COALESCE(EXCLUDED.sector, startups_discovered.sector),
    official_website = COALESCE(EXCLUDED.official_website, startups_discovered.official_website),
    -- high_priority e "pegajoso": uma vez marcado, nunca rebaixa.
    status = CASE
        WHEN startups_discovered.status = 'high_priority'
             OR EXCLUDED.status = 'high_priority'
        THEN 'high_priority'
        ELSE startups_discovered.status
    END;
"""


class Database:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self._settings.database_url,
                min_size=1,
                max_size=10,
            )
            logger.info("Pool de conexoes PostgreSQL inicializado.")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Pool de conexoes fechado.")

    async def migrate(self) -> None:
        assert self._pool is not None, "connect() deve ser chamado antes de migrate()"
        for sql_file in sorted(_SQL_DIR.glob("*.sql")):
            logger.info("Aplicando migracao %s", sql_file.name)
            async with self._pool.acquire() as conn:
                await conn.execute(sql_file.read_text(encoding="utf-8"))

    async def upsert_many(self, records: list[StartupRecord]) -> int:
        """Insere/atualiza em lote. Retorna a quantidade de registros validos enviados."""
        assert self._pool is not None, "connect() deve ser chamado antes de upsert_many()"
        rows = [r.as_upsert_tuple() for r in records if r.is_valid()]
        if not rows:
            return 0
        async with self._pool.acquire() as conn:
            await conn.executemany(_UPSERT_SQL, rows)
        logger.info("Upsert de %d registros concluido.", len(rows))
        return len(rows)

    async def fetch_seed_websites(self) -> list[str]:
        """Sementes para a busca aberta: sites oficiais distintos ja no banco."""
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            recs = await conn.fetch(
                "SELECT DISTINCT official_website FROM startups_discovered "
                "WHERE official_website IS NOT NULL AND official_website <> ''"
            )
        return [r["official_website"] for r in recs]

    # ------------------------------------------------------------------
    # Fase 2 — Deep Scan
    # ------------------------------------------------------------------

    async def fetch_pending_deep_scan(
        self,
        batch_size: int,
        statuses: list[str] | None = None,
    ) -> list[asyncpg.Record]:
        """Busca um lote de startups a processar.

        FOR UPDATE SKIP LOCKED garante que execucoes paralelas futuras nao
        peguem a mesma linha. Dentro de uma transacao implicita do acquire().
        """
        assert self._pool is not None
        if statuses is None:
            statuses = ["pending_deep_scan", "high_priority"]
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                return await conn.fetch(
                    "SELECT id, name, official_website, sector "
                    "FROM startups_discovered "
                    "WHERE status = ANY($1::text[]) "
                    "LIMIT $2 "
                    "FOR UPDATE SKIP LOCKED",
                    statuses,
                    batch_size,
                )

    async def update_startup_status(self, startup_id: int, status: str) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE startups_discovered SET status=$1, updated_at=CURRENT_TIMESTAMP WHERE id=$2",
                status,
                startup_id,
            )

    async def insert_chunks(self, chunks: list[tuple]) -> int:
        """Insere chunks na tabela startups_content em lote.

        Cada tupla: (startup_id, chunk_type, content, source_url, has_ai_signals, collected_at)
        """
        assert self._pool is not None
        if not chunks:
            return 0
        async with self._pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO startups_content "
                "(startup_id, chunk_type, content, source_url, has_ai_signals, collected_at) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                chunks,
            )
        return len(chunks)

    async def summary(self) -> list[asyncpg.Record]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            return await conn.fetch(
                "SELECT source_name, status, count(*) AS total "
                "FROM startups_discovered GROUP BY source_name, status "
                "ORDER BY source_name, status"
            )
