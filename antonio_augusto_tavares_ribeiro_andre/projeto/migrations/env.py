"""Ambiente Alembic do TAPI (F0.6).

A URL vem da config central (`Settings.sqlalchemy_url`), e o `target_metadata` é o
`SQLModel.metadata` — importar `packages.db.models` registra todas as tabelas.
`render_as_batch=True` mantém futuras migrações compatíveis com SQLite (testes).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

from packages.config import get_settings
from packages.db import models  # noqa: F401  (registra as tabelas no metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL resolvida em runtime (Postgres em prod; SQLite via POSTGRES_URL nos testes).
config.set_main_option("sqlalchemy.url", get_settings().sqlalchemy_url)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
