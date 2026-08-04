from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from .postgres import create_postgres_engine
from .sql_models import Base


def create_all_tables() -> None:
    """
    Bootstrap opcional da camada estruturada.
    TODO: substituir por migrations quando o schema estabilizar.
    """
    engine = create_postgres_engine()
    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Falha ao criar tabelas estruturadas: {exc}") from exc
