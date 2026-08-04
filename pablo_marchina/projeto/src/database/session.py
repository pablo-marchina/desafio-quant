"""SQLAlchemy runtime for the transactional product database."""

from __future__ import annotations

import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base

DEFAULT_PRODUCT_DB_URL = "sqlite:///data/product/product.db"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ProductDatabaseRuntime:
    url: str
    engine: Engine
    session_factory: sessionmaker[Session]


_runtime: ProductDatabaseRuntime | None = None


def get_product_db_url() -> str:
    value = os.getenv("PRODUCT_DB_URL")
    if value:
        return value
    if os.getenv("APP_MODE", "product").lower() == "product":
        msg = "PRODUCT_DB_URL is required when APP_MODE=product"
        raise RuntimeError(msg)
    return DEFAULT_PRODUCT_DB_URL


def sanitize_database_url(database_url: str) -> str:
    url = make_url(database_url)
    return url.render_as_string(hide_password=True)


def _ensure_sqlite_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _is_product_mode() -> bool:
    return os.getenv("APP_MODE", "").casefold() == "product"


def build_product_database(database_url: str | None = None) -> ProductDatabaseRuntime:
    url = database_url or get_product_db_url()
    backend = make_url(url).get_backend_name()
    if _is_product_mode() and not backend.startswith("postgresql"):
        msg = "APP_MODE=product requires PRODUCT_DB_URL to use PostgreSQL"
        raise RuntimeError(msg)
    _ensure_sqlite_directory(url)
    connect_args = {"check_same_thread": False} if backend == "sqlite" else {}
    engine = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    return ProductDatabaseRuntime(url=url, engine=engine, session_factory=factory)


def assert_product_schema_current(engine: Engine) -> None:
    """Fail closed unless the database revision exactly matches Alembic head."""
    try:
        from alembic.config import Config
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory
    except ImportError as exc:  # pragma: no cover - Alembic is a product dependency
        raise RuntimeError("Alembic is required to validate the production database schema") from exc

    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)
    expected_heads = set(script.get_heads())
    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())

    if current_heads != expected_heads:
        current = ", ".join(sorted(current_heads)) or "<none>"
        expected = ", ".join(sorted(expected_heads)) or "<none>"
        raise RuntimeError(
            "Product database schema is not current "
            f"(current={current}, expected={expected}). Run `python -m alembic upgrade head`."
        )


def configure_product_database(
    database_url: str | None = None,
    *,
    create_schema: bool = True,
) -> ProductDatabaseRuntime:
    global _runtime
    if _runtime is not None:
        _runtime.engine.dispose()
    _runtime = build_product_database(database_url)
    if create_schema:
        if _is_product_mode():
            assert_product_schema_current(_runtime.engine)
        else:
            Base.metadata.create_all(_runtime.engine)
    return _runtime


def get_product_database() -> ProductDatabaseRuntime:
    global _runtime
    if _runtime is None:
        _runtime = configure_product_database()
    return _runtime


def initialize_product_database() -> ProductDatabaseRuntime:
    runtime = get_product_database()
    if _is_product_mode():
        assert_product_schema_current(runtime.engine)
    else:
        Base.metadata.create_all(runtime.engine)
    return runtime


def get_db_session() -> Generator[Session, None, None]:
    session = get_product_database().session_factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def product_session() -> Iterator[Session]:
    session = get_product_database().session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_product_database() -> tuple[bool, str | None]:
    try:
        runtime = get_product_database()
        with runtime.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def reset_product_database_runtime() -> None:
    global _runtime
    if _runtime is not None:
        _runtime.engine.dispose()
    _runtime = None
