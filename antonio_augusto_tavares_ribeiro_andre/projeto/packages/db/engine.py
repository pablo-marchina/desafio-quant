"""Engine e sessões SQLModel (F0.6).

Usa a config central (F0.3): `Settings.sqlalchemy_url` já força o driver psycopg v3.
O engine é cacheado por URL. `get_session` serve como dependência (FastAPI, F5).
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlmodel import Session, create_engine

from packages.config import get_settings


@lru_cache
def get_engine(url: str | None = None):
    """Engine cacheado. `url` explícito sobrepõe a config (ex.: testes em SQLite)."""
    resolved = url or get_settings().sqlalchemy_url
    return create_engine(resolved, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """Sessão por requisição (dependência). Fecha ao final do escopo."""
    with Session(get_engine()) as session:
        yield session
