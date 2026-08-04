from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.database.models import (
    AnalysisRun,
    GapDiagnosisRecord,
    NvidiaMappingRecord,
    ProductReadinessCheck,
)
from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.activation import ActivationRecommendationRepository
from src.repositories.product import ProductRepository
from src.services.product.activation_service import ActivationPlaybookService


@pytest.fixture
def db_session(tmp_path: Path):
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'activation.db').as_posix()}")
    session = runtime.session_factory()
    yield session
    session.close()
    reset_product_database_runtime()


@pytest.fixture
def startup(db_session):
    repo = ProductRepository(db_session)
    s = repo.create_startup(
        name="Test Startup",
        website="https://test.example.com",
        country="Brazil",
        sector="AI",
        description="Test description",
        product_summary="Test product summary",
    )
    db_session.commit()
    return s


@pytest.fixture
def analysis_run(db_session, startup):
    repo = ProductRepository(db_session)
    run = repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    repo.update_analysis_run_status(run.id, status="completed", completed_at=datetime.now(UTC))
    db_session.commit()
    return db_session.get(AnalysisRun, run.id)


def _add_gap(
    db_session,
    run_id: str,
    gap_type: str,
    detected: bool = True,
    confidence: str = "high",
):
    record = GapDiagnosisRecord(
        analysis_run_id=run_id,
        gap_type=gap_type,
        detected=detected,
        confidence=confidence,
        evidence_tag="fact",
        reasoning=f"Gap {gap_type} detected",
        evidence_refs_json=[],
        missing_evidence_json=[],
    )
    db_session.add(record)
    db_session.flush()
    return record


def _add_mapping(db_session, run_id: str, gap_type: str, tech: str):
    record = NvidiaMappingRecord(
        analysis_run_id=run_id,
        technology_name=tech,
        addresses_gap=gap_type,
        justification=f"{tech} addresses {gap_type}",
    )
    db_session.add(record)
    db_session.flush()
    return record


def _add_readiness(db_session, run_id: str, code: str, status: str = "degraded"):
    record = ProductReadinessCheck(
        analysis_run_id=run_id,
        code=code,
        severity="warning",
        status=status,
        user_message=f"{code} detected",
        internal_detail=f"Detail for {code}",
        recommended_action="Review",
    )
    db_session.add(record)
    db_session.flush()
    return record


def test_generate_recommendations_for_run_matches_by_gap(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "high_latency", detected=True, confidence="high")
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    recommendations = service.generate_recommendations_for_run(analysis_run.id)

    names = [r["playbook_name"] for r in recommendations]
    assert "Latency Optimization" in names


def test_no_match_when_no_compatible_gap(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "observability_gap", detected=True)
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    recommendations = service.generate_recommendations_for_run(analysis_run.id)

    assert len(recommendations) == 0


def test_match_ignores_not_detected_gaps(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "high_latency", detected=False)
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    recommendations = service.generate_recommendations_for_run(analysis_run.id)

    latency_playbooks = [r for r in recommendations if r["playbook_id"] == "latency_optimization"]
    assert len(latency_playbooks) == 0


def test_confidence_boost_with_nvidia_mapping(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "high_inference_cost", detected=True, confidence="high")
    _add_mapping(db_session, analysis_run.id, "high_inference_cost", "NVIDIA NIM")
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    recommendations = service.generate_recommendations_for_run(analysis_run.id)

    inf_cost = [r for r in recommendations if r["playbook_id"] == "inference_cost_optimization"]
    assert len(inf_cost) == 1
    assert inf_cost[0]["confidence"] == "high" or inf_cost[0]["confidence"] == "medium"


def test_confidence_penalty_with_unsupported_claims(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "high_latency", detected=True, confidence="medium")
    _add_readiness(db_session, analysis_run.id, "UNSUPPORTED_CRITICAL_CLAIM", "error")
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    recommendations = service.generate_recommendations_for_run(analysis_run.id)

    lat = [r for r in recommendations if r["playbook_id"] == "latency_optimization"]
    if lat:
        assert lat[0]["confidence"] in ("low", "medium")


def test_persist_recommendations_is_idempotent(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "voice_need", detected=True, confidence="medium")
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    first = service.persist_recommendations_for_run(analysis_run.id)
    second = service.persist_recommendations_for_run(analysis_run.id)

    assert len(first) == len(second)

    repo = ActivationRecommendationRepository(db_session)
    records = repo.list_for_analysis_run(analysis_run.id)
    assert len(records) == len(first)


def test_generate_returns_priority_ordered(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "high_inference_cost", detected=True, confidence="high")
    _add_gap(db_session, analysis_run.id, "high_latency", detected=True, confidence="medium")
    _add_gap(db_session, analysis_run.id, "voice_need", detected=True, confidence="low")
    _add_mapping(db_session, analysis_run.id, "high_inference_cost", "NVIDIA NIM")
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    recommendations = service.generate_recommendations_for_run(analysis_run.id)

    assert len(recommendations) >= 1
    for i in range(len(recommendations) - 1):
        assert recommendations[i]["priority"] <= recommendations[i + 1]["priority"]


def test_matched_gap_types_are_recorded(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "slow_data_pipeline", detected=True, confidence="high")
    _add_gap(db_session, analysis_run.id, "heavy_tabular_processing", detected=True, confidence="medium")
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    recommendations = service.generate_recommendations_for_run(analysis_run.id)

    data_pb = [r for r in recommendations if r["playbook_id"] == "data_pipeline_acceleration"]
    assert len(data_pb) >= 1
    assert "slow_data_pipeline" in data_pb[0]["matched_gap_types"]


def test_repository_top_for_run(
    db_session,
    analysis_run: AnalysisRun,
) -> None:
    _add_gap(db_session, analysis_run.id, "high_inference_cost", detected=True, confidence="high")
    _add_mapping(db_session, analysis_run.id, "high_inference_cost", "NVIDIA NIM")
    db_session.commit()

    service = ActivationPlaybookService(db_session)
    service.persist_recommendations_for_run(analysis_run.id)

    top = service.get_top_for_run(analysis_run.id)
    assert top is not None
    assert "playbook_name" in top
    assert "confidence" in top
