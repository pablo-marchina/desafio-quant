from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def test_alembic_metadata_imports() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1
    head = script.get_revision(heads[0])
    assert head is not None
    assert head.doc in (
        "create all product entities",
        "create claim_records",
        "create activation_dossier_records",
        "create opportunity_score_records table",
        "add review_decision audit columns",
    )


def test_alembic_env_prefers_product_db_url_in_product_mode() -> None:
    env_source = (PROJECT_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
    assert 'os.getenv("APP_MODE") == "product"' in env_source
    assert 'if os.getenv("APP_MODE") == "product" and product_database_url' in env_source
    assert "else configured_database_url or product_database_url" in env_source


def test_alembic_upgrade_and_downgrade_sqlite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.delenv("PRODUCT_DB_URL", raising=False)

    db_path = tmp_path / "test_migrate.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    from alembic import command
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(config, "head")
    engine = None
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url)
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
            "claim_records",
            "activation_dossier_records",
            "opportunity_score_records",
        }
        assert required.issubset(tables), f"Missing tables: {required - set(tables)}"
        assert "alembic_version" in tables

        # Verify new columns exist at head
        with engine.connect() as conn:
            rd_cols = {row[1] for row in conn.execute(text("PRAGMA table_info('review_decisions')"))}
        for col in (
            "startup_id",
            "thread_id",
            "review_payload_snapshot",
            "status_before_resume",
            "status_after_resume",
        ):
            assert col in rd_cols, f"Column {col} should exist at head"

        tables_before_opportunity_migration = {
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
            "claim_records",
            "activation_recommendations",
            "activation_dossier_records",
            "discovery_runs",
            "startup_discovery_candidates",
            "workflow_runs",
            "workflow_node_runs",
        }

        command.downgrade(config, "-1")
        with engine.connect() as conn:
            rd_cols_after = {row[1] for row in conn.execute(text("PRAGMA table_info('review_decisions')"))}
        for col in (
            "startup_id",
            "thread_id",
            "review_payload_snapshot",
            "status_before_resume",
            "status_after_resume",
        ):
            assert col not in rd_cols_after, f"Column {col} should have been removed by downgrade"

        tables_after = inspect(engine).get_table_names()
        remaining = set(tables_after) - {"alembic_version"}
        assert (
            "opportunity_score_records" in tables_after
        ), "opportunity_score_records should still exist (downgrade only reverted audit columns)"
        missing_tables = tables_before_opportunity_migration - remaining
        assert tables_before_opportunity_migration.issubset(
            remaining
        ), f"Tables before audit-column migration missing: {missing_tables}"
    finally:
        if engine is not None:
            engine.dispose()
