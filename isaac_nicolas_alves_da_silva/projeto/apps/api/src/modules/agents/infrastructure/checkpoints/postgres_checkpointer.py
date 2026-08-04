"""Checkpointer PostgreSQL para LangGraph.

Envolve ``AsyncPostgresSaver`` de ``langgraph-checkpoint-postgres`` e gerencia
o ciclo de vida do pool de conexoes psycopg de forma lazy: o pool so e aberto
na primeira chamada a ``get_saver()``, o que permite criar a instancia de forma
sincrona dentro da factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class PostgresCheckpointer:
    """Gerencia o ciclo de vida do AsyncPostgresSaver."""

    def __init__(self, conn_string: str) -> None:
        self._conn_string = conn_string
        self._pool: Any = None
        self._saver: AsyncPostgresSaver | None = None

    async def get_saver(self) -> "AsyncPostgresSaver":
        """Retorna o saver, abrindo o pool e criando tabelas na primeira chamada."""

        if self._saver is None:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            self._pool = AsyncConnectionPool(
                self._conn_string,
                open=False,
                kwargs={"autocommit": True},
            )
            await self._pool.open()
            self._saver = AsyncPostgresSaver(self._pool)
            # setup() e idempotente — cria tabelas se nao existirem.
            # Em producao as tabelas ja sao criadas pela migration Alembic,
            # mas chamamos aqui para garantir robustez em ambientes de dev/test.
            await self._saver.setup()

        return self._saver

    async def close(self) -> None:
        """Fecha o pool de conexoes (chamado no shutdown do worker)."""

        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._saver = None
