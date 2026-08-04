"""Engine e sessões assíncronas compartilhadas pelo banco relacional."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.src.config.settings import get_settings

# Registra todos os models no Base.metadata antes de qualquer sessao real usar
# repositories que possuam FKs entre modulos.
from apps.api.src.database.relational import models as _models  # noqa: F401


# O engine administra conexões com o PostgreSQL. Ele não representa uma conexão
# única; internamente, mantém um pool reutilizado pelas operações da aplicação.
engine: AsyncEngine = create_async_engine(
    get_settings().database_url,
    # Em desenvolvimento, esta verificação evita reutilizar uma conexão que o
    # PostgreSQL encerrou enquanto estava parada no pool.
    pool_pre_ping=True,
)


# A session factory cria unidades de trabalho independentes. Cada repositório
# usará uma AsyncSession para consultar, alterar e confirmar dados.
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def check_database_connection() -> bool:
    """Executa uma consulta mínima para verificar a conexão com o PostgreSQL."""

    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))

    return result.scalar_one() == 1
