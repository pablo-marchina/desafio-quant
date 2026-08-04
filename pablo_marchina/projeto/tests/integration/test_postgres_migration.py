from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text

PG_URL = os.getenv("PRODUCT_DB_TEST_URL", "")
REQUIRES_PG = pytest.mark.skipif(not PG_URL, reason="PRODUCT_DB_TEST_URL not set")


@REQUIRES_PG
def test_postgres_alembic_upgrade_creates_tables() -> None:
    from alembic import command
    from alembic.config import Config

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    alembic_ini = os.path.join(project_root, "alembic.ini")

    config = Config(alembic_ini)
    config.set_main_option("sqlalchemy.url", PG_URL)

    command.upgrade(config, "head")

    engine = create_engine(PG_URL)
    try:
        tables = inspect(engine).get_table_names()
        required = {
            "startups",
            "startup_evidence",
            "analysis_runs",
            "score_records",
            "gap_diagnosis_records",
            "nvidia_mapping_records",
            "action_brief_records",
            "product_readiness_checks",
            "review_decisions",
            "export_records",
        }
        assert required.issubset(set(tables)), f"Missing: {required - set(tables)}"

        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = 'startups' ORDER BY ordinal_position"
                )
            )
            columns = {row[0]: row[1] for row in result}
            assert "id" in columns
            assert "name" in columns
            assert "normalized_name" in columns
    finally:
        engine.dispose()
        command.downgrade(config, "-1")
        command.upgrade(config, "head")


@REQUIRES_PG
def test_postgres_json_columns_work() -> None:
    from alembic import command
    from alembic.config import Config

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    alembic_ini = os.path.join(project_root, "alembic.ini")

    config = Config(alembic_ini)
    config.set_main_option("sqlalchemy.url", PG_URL)
    command.upgrade(config, "head")

    engine = create_engine(PG_URL)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO startups "
                    "(id, name, normalized_name, website, sector, tags_json) "
                    "VALUES ('test-1', 'PG Startup', 'pg startup', "
                    "'https://pg.example.com', 'AI', "
                    '\'["tag1","tag2"]\'::json)'
                )
            )
            conn.commit()

            result = conn.execute(text("SELECT tags_json FROM startups WHERE id = 'test-1'"))
            row = result.fetchone()
            assert row is not None
            assert row[0] == ["tag1", "tag2"]
    finally:
        engine.dispose()
        command.downgrade(config, "-1")
        command.upgrade(config, "head")


@REQUIRES_PG
def test_postgres_repository_smoke() -> None:
    from alembic import command
    from alembic.config import Config

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    alembic_ini = os.path.join(project_root, "alembic.ini")
    config = Config(alembic_ini)
    config.set_main_option("sqlalchemy.url", PG_URL)
    command.upgrade(config, "head")

    from sqlalchemy.orm import sessionmaker

    from src.repositories.product import ProductRepository

    engine = create_engine(PG_URL)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        repo = ProductRepository(session)
        startup = repo.create_startup(
            name="PG Smoke",
            website="https://pg-smoke.example.com",
            country="Brazil",
            sector="AI",
        )
        session.commit()

        loaded = repo.get_startup(startup.id)
        assert loaded is not None
        assert loaded.name == "PG Smoke"

        updated = repo.update_startup_fields(startup.id, {"sector": "AI Infrastructure"})
        session.commit()
        assert updated is not None
        assert updated.sector == "AI Infrastructure"
    finally:
        session.close()
        engine.dispose()
        command.downgrade(config, "-1")
        command.upgrade(config, "head")
