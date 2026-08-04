from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect


def test_alembic_schema_contains_workflow_node_timestamps(tmp_path: Path) -> None:
    database_path = tmp_path / "workflow-schema.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    repository_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.update(
        {
            "APP_MODE": "product",
            "PRODUCT_DB_URL": database_url,
        }
    )

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
        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("workflow_node_runs")
        }
    finally:
        engine.dispose()

    assert "created_at" in columns
    assert "updated_at" in columns
    assert columns["updated_at"]["nullable"] is False
