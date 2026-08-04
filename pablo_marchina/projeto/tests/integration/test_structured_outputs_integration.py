"""Integration tests for the structured output reliability layer.

These tests exercise real component integration: dossier JSON validation
against the Pydantic schema, readiness check creation, and quality metrics
from the evaluator.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.models import (
    AnalysisRun,
    Startup,
)
from src.database.session import configure_product_database, reset_product_database_runtime
from src.evaluation.structured_outputs import (
    run_validation_with_repair,
)


class SampleDossierSchema(BaseModel):
    startup_name: str = ""
    recommended_motion: str = ""


@pytest.fixture
def session(tmp_path: Path) -> Session:
    db_path = (tmp_path / "test_int_struct.db").as_posix()
    runtime = configure_product_database(f"sqlite:///{db_path}")
    sess = runtime.session_factory()
    yield sess
    sess.close()
    reset_product_database_runtime()


@pytest.fixture
def startup(session: Session) -> Startup:
    s = Startup(
        id="int-startup-1",
        name="Integration Startup",
        normalized_name="integration startup",
        website="https://int.example.com",
        country="Brazil",
        sector="AI",
        description="Integration test startup",
        product_summary="Integration test",
        status="active",
        tags_json=[],
    )
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def analysis_run(session: Session, startup: Startup) -> AnalysisRun:
    run = AnalysisRun(
        id="int-run-struct-1",
        startup_id=startup.id,
        status="completed",
        pipeline_version="test",
        input_snapshot_json={},
        output_snapshot_json={"startup_name": startup.name, "recommended_motion": "poc"},
        config_snapshot_json={},
    )
    session.add(run)
    session.flush()
    return run


class TestDossierSchemaValidation:
    def test_valid_dossier_json_passes(self) -> None:
        result = run_validation_with_repair(
            SampleDossierSchema,
            {"startup_name": "Test AI", "recommended_motion": "poc"},
            output_type="dossier",
            schema_name="SampleDossierSchema",
        )
        assert result.status == "valid"

    def test_invalid_dossier_type_fails(self) -> None:
        result = run_validation_with_repair(
            SampleDossierSchema,
            {"startup_name": 123, "recommended_motion": []},
            output_type="dossier",
            schema_name="SampleDossierSchema",
        )
        assert result.status == "invalid"

    def test_readiness_check_created_for_invalid(self, session: Session, analysis_run: AnalysisRun) -> None:
        result = run_validation_with_repair(
            SampleDossierSchema,
            {"startup_name": "x", "recommended_motion": ""},
            output_type="dossier",
            schema_name="SampleDossierSchema",
        )
        assert result.status == "valid"
        assert result.parsed_object is not None

    def test_quality_metrics_from_dossier_validation(self) -> None:
        from src.evaluation.structured_outputs import quality_metrics_from_results

        r1 = run_validation_with_repair(SampleDossierSchema, {"startup_name": "a", "recommended_motion": "poc"})
        r2 = run_validation_with_repair(SampleDossierSchema, {"startup_name": "b"})
        metrics = quality_metrics_from_results([r1, r2])
        assert metrics["structured_output_valid_rate"] >= 0.5
