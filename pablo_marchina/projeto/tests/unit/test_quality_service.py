from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.database.models import (
    ActivationDossierRecord,
    AnalysisRun,
    ClaimRecord,
    Startup,
)
from src.database.session import configure_product_database, reset_product_database_runtime
from src.quality.constants import (
    METRIC_EVIDENCE_COVERAGE,
    METRIC_EXPORT_READINESS_SCORE,
    METRIC_REVIEW_READINESS_SCORE,
)
from src.quality.service import ProductQualityService


@pytest.fixture
def session(tmp_path: Path) -> Session:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'svc.db').as_posix()}")
    sess = runtime.session_factory()
    yield sess
    sess.close()
    reset_product_database_runtime()


@pytest.fixture
def seeded_session(session: Session) -> Session:
    startup = Startup(
        id="startup-svc",
        name="Svc Startup",
        normalized_name="svc startup",
        website="https://svc.example.com",
        country="Brazil",
        sector="AI",
        description="Test",
        product_summary="Test",
        status="active",
        tags_json=[],
    )
    session.add(startup)
    run = AnalysisRun(
        id="run-svc-1",
        startup_id=startup.id,
        status="completed",
        pipeline_version="test",
        input_snapshot_json={},
        output_snapshot_json={"startup_name": startup.name, "recommended_motion": "poc"},
        config_snapshot_json={},
    )
    session.add(run)
    session.add(
        ClaimRecord(
            id="c-svc-1",
            startup_id=startup.id,
            analysis_run_id=run.id,
            claim_text="Claim 1",
            claim_type="ai_native_claim",
            support_level="strong",
            confidence="high",
            evidence_refs_json=[{}],
            used_in_score=True,
            used_in_gap=False,
            used_in_mapping=False,
            used_in_brief=False,
            review_status="unreviewed",
            reviewer_notes="",
            metadata_json={},
        )
    )
    session.add(
        ClaimRecord(
            id="c-svc-2",
            startup_id=startup.id,
            analysis_run_id=run.id,
            claim_text="Claim 2",
            claim_type="technical_stack_claim",
            support_level="unsupported",
            confidence="low",
            evidence_refs_json=[],
            used_in_score=True,
            used_in_gap=False,
            used_in_mapping=False,
            used_in_brief=False,
            review_status="unreviewed",
            reviewer_notes="",
            metadata_json={},
        )
    )
    session.add(
        ActivationDossierRecord(
            id="dossier-svc",
            analysis_run_id=run.id,
            version=1,
            schema_version="1.0",
            dossier_json={
                "metadata": {"version": "1"},
                "startup": {"name": "Test"},
                "executive_verdict": "good",
                "evidence_summary": {"total": 2},
                "claims": [],
                "scores": [],
                "gaps": [],
                "nvidia_mappings": [],
                "activation_recommendations": [],
                "risks": [],
                "uncertainties": [],
                "review": {"status": "pending"},
                "next_action": "review",
            },
            dossier_markdown="# Dossier",
            is_latest=True,
            evidence_coverage=0.5,
            unsupported_claim_count=1,
            recommended_motion="poc",
        )
    )
    session.flush()
    return session


def test_run_quality_evaluation_creates_run(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    quality_run = svc.run_quality_evaluation_for_analysis_run("run-svc-1")
    assert quality_run is not None
    assert quality_run.status in ("completed", "degraded")
    assert quality_run.analysis_run_id == "run-svc-1"


def test_run_quality_evaluation_persists_metrics(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    quality_run = svc.run_quality_evaluation_for_analysis_run("run-svc-1")
    metrics = svc.repository.get_metrics_for_quality_run(quality_run.id)
    assert len(metrics) > 0
    metric_names = {m.metric_name for m in metrics}
    assert METRIC_EVIDENCE_COVERAGE in metric_names


def test_run_quality_evaluation_summary(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    quality_run = svc.run_quality_evaluation_for_analysis_run("run-svc-1")
    assert quality_run.summary_json is not None
    assert quality_run.summary_json.get("total_metrics", 0) > 0
    assert quality_run.summary_json.get("overall_status") is not None


def test_get_latest_quality_run_returns_none_for_missing(session: Session) -> None:
    svc = ProductQualityService(session)
    assert svc.get_latest_quality_run("nonexistent") is None


def test_get_latest_quality_run_after_evaluation(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    svc.run_quality_evaluation_for_analysis_run("run-svc-1")
    latest = svc.get_latest_quality_run("run-svc-1")
    assert latest is not None
    assert latest.analysis_run_id == "run-svc-1"


def test_summarize_quality_result_no_run(session: Session) -> None:
    svc = ProductQualityService(session)
    summary = svc.summarize_quality_result("nonexistent")
    assert summary["overall_status"] == "no_quality_run"
    assert summary["quality_run_id"] is None


def test_summarize_quality_result_after_evaluation(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    svc.run_quality_evaluation_for_analysis_run("run-svc-1")
    summary = svc.summarize_quality_result("run-svc-1")
    assert summary["quality_run_id"] is not None
    assert summary["overall_status"] in ("pass", "warn", "degraded")
    assert summary["total_metrics"] > 0
    assert METRIC_EXPORT_READINESS_SCORE in summary["metrics"]
    assert METRIC_REVIEW_READINESS_SCORE in summary["metrics"]


def test_evaluate_dossier(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    result = svc.evaluate_dossier("run-svc-1")
    assert "dossier_section_completeness" in result
    assert result["dossier_exists"] is True


def test_evaluate_claim_support(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    result = svc.evaluate_claim_support("run-svc-1")
    assert "evidence_coverage" in result
    assert result["total_claims"] == 2


def test_evaluate_export_readiness(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    result = svc.evaluate_export_readiness("run-svc-1")
    assert "export_readiness_score" in result


def test_raise_on_nonexistent_analysis_run(session: Session) -> None:
    svc = ProductQualityService(session)
    with pytest.raises(LookupError):
        svc.run_quality_evaluation_for_analysis_run("missing-run")


def test_re_evaluation_deletes_previous_run(seeded_session: Session) -> None:
    svc = ProductQualityService(seeded_session)
    run1 = svc.run_quality_evaluation_for_analysis_run("run-svc-1")
    run2 = svc.run_quality_evaluation_for_analysis_run("run-svc-1")
    assert run1.id != run2.id
    runs = svc.repository.list_quality_runs_for_analysis_run("run-svc-1")
    assert len(runs) == 1
    assert runs[0].id == run2.id
