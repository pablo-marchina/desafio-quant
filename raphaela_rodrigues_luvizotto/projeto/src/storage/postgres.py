from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@dataclass
class PostgresSettings:
    database_url: str | None = os.environ.get("SUPABASE_DB_URL")


def create_postgres_engine(settings: PostgresSettings | None = None) -> Engine:
    settings = settings or PostgresSettings()
    if not settings.database_url:
        raise RuntimeError(
            "SUPABASE_DB_URL nao configurada. Defina a connection string do Supabase/Postgres."
        )
    return create_engine(settings.database_url, future=True)
