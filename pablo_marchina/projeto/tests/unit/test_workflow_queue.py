from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from src.database.models import Base
from src.database.session import configure_product_database, reset_product_database_runtime
from src.orchestration.service import WorkflowOrchestrationService
from src.orchestration.state import WorkflowStatus
from src.repositories.workflow import WorkflowRepository


def test_enqueue_claim_and_attach_analysis_workflow(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "test")
    reset_product_database_runtime()
    runtime = configure_product_database("sqlite:///:memory:")

    with runtime.session_factory() as session:
        service = WorkflowOrchestrationService(session)
        queued = service.enqueue_workflow(startup_id="startup-test", use_rag=True)
        assert queued.status == WorkflowStatus.QUEUED
        workflow_id = queued.id

    with runtime.session_factory() as session:
        repo = WorkflowRepository(session)
        claimed = repo.claim_next_queued_workflow()
        assert claimed is not None
        assert claimed.id == workflow_id
        assert claimed.status == WorkflowStatus.RUNNING
        attached = repo.attach_analysis_run(workflow_id, "analysis-test")
        assert attached is not None
        assert attached.analysis_run_id == "analysis-test"
        assert attached.state_json["analysis_run_id"] == "analysis-test"
        session.commit()

    with runtime.session_factory() as session:
        persisted = WorkflowRepository(session).get_workflow_run(workflow_id)
        assert persisted is not None
        assert persisted.analysis_run_id == "analysis-test"
        assert WorkflowRepository(session).claim_next_queued_workflow() is None

    reset_product_database_runtime()


def test_enqueue_requires_a_target(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODE", "test")
    reset_product_database_runtime()
    runtime = configure_product_database("sqlite:///:memory:")

    with runtime.session_factory() as session:
        service = WorkflowOrchestrationService(session)
        try:
            service.enqueue_workflow(use_rag=True)
        except ValueError as exc:
            assert "required" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("enqueue_workflow should reject a targetless workflow")

    reset_product_database_runtime()


def test_alembic_schema_contains_every_orm_table_and_column(tmp_path: Path) -> None:
    database_path = tmp_path / "model-parity.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    repository_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.update({"APP_MODE": "product", "PRODUCT_DB_URL": database_url})

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=repository_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    try:
        database_inspector = inspect(engine)
        database_tables = set(database_inspector.get_table_names())
        missing_tables: dict[str, list[str]] = {}
        missing_columns: dict[str, list[str]] = {}

        for model_table in Base.metadata.sorted_tables:
            if model_table.name not in database_tables:
                missing_tables[model_table.name] = sorted(column.name for column in model_table.columns)
                continue
            database_columns = {
                column["name"] for column in database_inspector.get_columns(model_table.name)
            }
            absent = sorted({column.name for column in model_table.columns} - database_columns)
            if absent:
                missing_columns[model_table.name] = absent
    finally:
        engine.dispose()

    assert not missing_tables, missing_tables
    assert not missing_columns, missing_columns
