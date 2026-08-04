"""Ponto de entrada do Alembic.

Este arquivo é executado sempre que rodamos `alembic revision --autogenerate`
ou `alembic upgrade/downgrade`. Ele conecta três coisas:

1. A configuração da aplicação (Settings/.env) -> de onde vem a DATABASE_URL.
2. O Base.metadata do SQLAlchemy -> o "catálogo" de todas as tabelas
   conhecidas pelos models.
3. O Alembic em si -> que compara (1) com (2) e decide o que mudou.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# --- Configuração da aplicação -------------------------------------------
# Importamos o Settings real para reutilizar a mesma DATABASE_URL usada pela
# API e pelos workers. Assim, não existe um valor de banco "duplicado" só
# para as migrations.
from apps.api.src.config.settings import get_settings

# --- Base e models ----------------------------------------------------
# Importar a Base é obrigatório: é dela que vem o `metadata` usado no
# autogenerate. Importar cada model também é obrigatório, ainda que pareçam
# "não usados" — é só importando a classe que ela se registra em
# Base.metadata. Sem esses imports, o Alembic acharia que as tabelas não
# existem e tentaria APAGÁ-LAS num autogenerate.
from apps.api.src.database.relational.base import Base
from apps.api.src.modules.scraping.infrastructure.database.models import (  # noqa: F401
    scraping_attempt_model,
    scraping_job_model,
    scraping_result_model,
)
from apps.api.src.modules.agents.infrastructure.database.models import (  # noqa: F401
    agent_run_model,
    agent_step_model,
)
from apps.api.src.modules.ingestion.infrastructure.database.models import (  # noqa: F401
    chunk_model,
    document_model,
    ingestion_job_model,
)
from apps.api.src.modules.embeddings.infrastructure.database.models import (  # noqa: F401
    embedding_job_chunk_model,
    embedding_job_model,
)
from apps.api.src.modules.startups.infrastructure.database.models import (  # noqa: F401
    startup_evidence_model,
    startup_model,
)
from apps.api.src.modules.recommendations.infrastructure.database.models import (  # noqa: F401
    recommendation_model,
)
from apps.api.src.modules.briefing.infrastructure.database.models import (  # noqa: F401
    briefing_model,
)
from apps.api.src.modules.orchestration.infrastructure.database.models import (  # noqa: F401
    analysis_job_model,
)

# Objeto de configuração do Alembic, vindo do alembic.ini.
config = context.config

# Configura o logging do Alembic conforme as seções [logger_*] do .ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `target_metadata` é o que o autogenerate usa para comparar com o banco real.
target_metadata = Base.metadata

# Sobrescrevemos a URL do banco definida no alembic.ini (que está vazia de
# propósito) com a URL real vinda do .env, através do Settings.
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    """Gera SQL sem se conectar ao banco (modo `alembic upgrade --sql`).

    Útil para revisar o SQL gerado antes de aplicá-lo manualmente, mas não é
    o modo que usaremos no dia a dia.
    """

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Executa as migrations usando uma conexão já aberta."""

    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Cria um engine assíncrono (asyncpg) e aplica as migrations.

    Este é o caminho usado no dia a dia: `alembic upgrade head` e
    `alembic revision --autogenerate` passam por aqui, porque nossa
    DATABASE_URL usa o driver assíncrono `postgresql+asyncpg`.
    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool: cada execução do Alembic é pontual (um comando de CLI),
        # então não vale a pena manter um pool de conexões vivo depois.
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync: a API do Alembic (context.configure, run_migrations) é
        # síncrona por natureza; run_sync executa esse código síncrono
        # dentro da conexão assíncrona.
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Ponto de entrada usado pelo Alembic em modo "online" (padrão)."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
