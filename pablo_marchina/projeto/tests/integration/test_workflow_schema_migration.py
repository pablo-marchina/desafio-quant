from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from src.repositories.workflow import WorkflowRepository


@pytest.mark.integration
def test_alembic_head_matches_workflow_node_timestamp_contract() -> None:
    database_url = os.environ.get("PRODUCT_DB_URL", "").strip()
    if not database_url or not database_url.startswith("postgresql"):
        pytest.skip("PRODUCT_DB_URL PostgreSQL is required")

    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        columns = {item["name"] for item in inspect(engine).get_columns("workflow_node_runs")}
        assert {"created_at", "updated_at"}.issubset(columns)

        with Session(engine) as session:
            repo = WorkflowRepository(session)
            workflow = repo.create_workflow_run(state_json={"migration_contract": True})
            node = repo.create_node_run(
                workflow_run_id=workflow.id,
                node_name="migration_contract",
                input_snapshot={"real_database": True},
            )
            repo.update_node_run_status(
                node.id,
                status="completed",
                output_snapshot={"schema_valid": True},
            )
            session.commit()
            session.refresh(node)

            assert node.created_at is not None
            assert node.updated_at is not None
            assert node.output_snapshot_json == {"schema_valid": True}
    finally:
        engine.dispose()
