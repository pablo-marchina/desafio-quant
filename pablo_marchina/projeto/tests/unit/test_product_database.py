from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from src.database.session import (
    configure_product_database,
    reset_product_database_runtime,
    sanitize_database_url,
)


def test_product_database_creates_sqlite_directory_and_schema(tmp_path: Path) -> None:
    import os
    from unittest.mock import patch

    database_path = tmp_path / "nested" / "product.db"
    with patch.dict(os.environ, {"APP_MODE": "test"}):
        runtime = configure_product_database(f"sqlite:///{database_path.as_posix()}")

    assert database_path.exists()
    assert {
        "startups",
        "startup_evidence",
        "analysis_runs",
        "score_records",
        "gap_diagnosis_records",
        "nvidia_mapping_records",
        "action_brief_records",
        "product_readiness_checks",
    }.issubset(inspect(runtime.engine).get_table_names())
    reset_product_database_runtime()


def test_sanitize_database_url_hides_password() -> None:
    sanitized = sanitize_database_url("postgresql://user:secret@localhost:5432/radar")

    assert "secret" not in sanitized
    assert "***" in sanitized


def test_product_modules_do_not_reference_demo_runs() -> None:
    """Regression: product services must not read data/demo_runs.

    Product flow uses persisted entities configured by PRODUCT_DB_URL.
    The data/demo_runs/ directory exists only for legacy demo scripts and CLI.
    """
    product_dirs = [
        "src/database",
        "src/repositories",
        "src/services/product",
        "src/api/product_routes.py",
        "src/api/product_schemas.py",
    ]
    project_root = Path(__file__).resolve().parent.parent.parent
    for path in product_dirs:
        target = project_root / path
        if target.is_file():
            files = [target]
        else:
            files = list(target.rglob("*.py"))
        for f in files:
            text = f.read_text(encoding="utf-8")
            if "demo_runs" in text:
                raise AssertionError(
                    f"Product module {f.relative_to(project_root)} contains "
                    f"'demo_runs' reference. Product code must not depend on demo artifacts."
                )
