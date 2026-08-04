from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.database.models import (
    ActivationDossierRecord,
    ActivationRecommendationRecord,
    AnalysisRun,
    ClaimRecord,
    ProductReadinessCheck,
    ReviewDecision,
    Startup,
)
from src.database.session import configure_product_database, reset_product_database_runtime
from src.quality.evaluators.activation_playbook import ActivationPlaybookEvaluator
from src.quality.evaluators.degraded_state import DegradedStateEvaluator
from src.quality.evaluators.dossier_completeness import DossierCompletenessEvaluator
from src.quality.evaluators.evidence_coverage import EvidenceCoverageEvaluator
from src.quality.evaluators.export_readiness import ExportReadinessEvaluator
from src.quality.evaluators.recommendation_actionability import (
    RecommendationActionabilityEvaluator,
)
from src.quality.evaluators.review_readiness import ReviewReadinessEvaluator


@pytest.fixture
def session(tmp_path: Path) -> Session:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'eval.db').as_posix()}")
    sess = runtime.session_factory()
    yield sess
    sess.close()
    reset_product_database_runtime()


@pytest.fixture
def startup(session: Session) -> Startup:
    s = Startup(
        id="startup-1",
        name="Eval Startup",
        normalized_name="eval startup",
        website="https://eval.example.com",
        country="Brazil",
        sector="AI",
        description="Test",
        product_summary="Test",
        status="active",
        tags_json=[],
    )
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def analysis_run(session: Session, startup: Startup) -> AnalysisRun:
    run = AnalysisRun(
        id="run-eval-1",
        startup_id=startup.id,
        status="completed",
        pipeline_version="test",
        input_snapshot_json={},
        output_snapshot_json={
            "startup_name": startup.name,
            "recommended_motion": "poc",
        },
        config_snapshot_json={},
    )
    session.add(run)
    session.flush()
    return run


def test_evidence_coverage_evaluator_empty(session: Session) -> None:
    ev = EvidenceCoverageEvaluator(session)
    result = ev.evaluate("nonexistent-run")
    assert result["evidence_coverage"] == 0.0
    assert result["total_claims"] == 0


def test_evidence_coverage_evaluator_with_claims(  # noqa: E501
    session: Session,
    startup: Startup,
    analysis_run: AnalysisRun,
) -> None:
    session.add_all(
        [
            ClaimRecord(
                id="c1",
                startup_id=startup.id,
                analysis_run_id=analysis_run.id,
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
            ),
            ClaimRecord(
                id="c2",
                startup_id=startup.id,
                analysis_run_id=analysis_run.id,
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
            ),
        ]
    )
    session.flush()

    ev = EvidenceCoverageEvaluator(session)
    result = ev.evaluate(analysis_run.id)
    assert result["total_claims"] == 2
    assert result["supported_claims"] == 1
    assert result["unsupported_claims"] == 1
    assert result["evidence_coverage"] == 0.5
    assert result["unsupported_claim_rate"] == 0.5


def test_dossier_completeness_evaluator_no_dossier(session: Session) -> None:
    dc = DossierCompletenessEvaluator(session)
    result = dc.evaluate("nonexistent")
    assert result["dossier_exists"] is False
    assert result["dossier_section_completeness"] == 0.0
    assert len(result["missing_required_sections"]) > 0


def test_dossier_completeness_evaluator_with_dossier(  # noqa: E501
    session: Session,
    startup: Startup,
    analysis_run: AnalysisRun,
) -> None:
    dossier = ActivationDossierRecord(
        id="dossier-1",
        analysis_run_id=analysis_run.id,
        version=1,
        schema_version="1.0",
        dossier_json={
            "metadata": {"version": "1"},
            "startup": {"name": "Test"},
            "executive_verdict": "good",
            "evidence_summary": {"total": 5},
            "claims": [{"id": "c1", "text": "Claim"}],
            "scores": [{"type": "inception", "value": 80}],
            "gaps": [{"type": "gap_1", "detected": True}],
            "nvidia_mappings": [{"technology": "cuda"}],
            "activation_recommendations": [{"playbook": "pb-1"}],
            "risks": [{"risk": "low adoption"}],
            "uncertainties": [{"source": "market"}],
            "review": {"status": "pending"},
            "next_action": "review",
        },
        dossier_markdown="# Test",
        is_latest=True,
        evidence_coverage=1.0,
        unsupported_claim_count=0,
        recommended_motion="poc",
    )
    session.add(dossier)
    session.flush()

    dc = DossierCompletenessEvaluator(session)
    result = dc.evaluate(analysis_run.id)
    assert result["dossier_exists"] is True
    assert result["dossier_section_completeness"] == 1.0
    assert len(result["missing_required_sections"]) == 0


def test_activation_playbook_evaluator_no_recommendations(session: Session) -> None:
    ap = ActivationPlaybookEvaluator(session)
    result = ap.evaluate("nonexistent")
    assert result["activation_playbook_present"] is False
    assert result["activation_playbook_evidence_support"] == 0.0


def test_activation_playbook_evaluator_with_recommendations(
    session: Session,
    startup: Startup,
    analysis_run: AnalysisRun,
) -> None:
    session.add(
        ActivationRecommendationRecord(
            id="rec-1",
            analysis_run_id=analysis_run.id,
            playbook_id="pb-1",
            playbook_name="Test Playbook",
            matched_gap_types_json=["gap_1"],
            matched_claim_ids_json=["c1"],
            nvidia_technologies_json=["cuda"],
            technical_experiment="Run benchmark",
            success_metrics_json=["latency"],
            recommended_motion="poc",
            priority=1,
            confidence="high",
            reasoning="Good fit",
            evidence_refs_json=[{}],
            risks_json=[],
            next_step="Setup environment",
        )
    )
    session.flush()

    ap = ActivationPlaybookEvaluator(session)
    result = ap.evaluate(analysis_run.id)
    assert result["activation_playbook_present"] is True
    assert result["top_confidence"] == "high"


def test_recommendation_actionability_evaluator_no_run(session: Session) -> None:
    ra = RecommendationActionabilityEvaluator(session)
    result = ra.evaluate("nonexistent")
    assert result["recommendation_actionability_score"] == 0.0
    assert result["has_recommended_motion"] is False


def test_recommendation_actionability_evaluator_full_score(
    session: Session,
    startup: Startup,
    analysis_run: AnalysisRun,
) -> None:
    session.add(
        ActivationRecommendationRecord(
            id="rec-action-1",
            analysis_run_id=analysis_run.id,
            playbook_id="pb-action",
            playbook_name="Action Playbook",
            matched_gap_types_json=["gap_1"],
            matched_claim_ids_json=["c1"],
            nvidia_technologies_json=["cuda"],
            technical_experiment="Run benchmark test",
            success_metrics_json=["latency", "throughput"],
            recommended_motion="poc",
            priority=1,
            confidence="high",
            reasoning="Good fit",
            evidence_refs_json=[{}],
            risks_json=[],
            next_step="Setup environment and run tests",
        )
    )
    session.flush()

    ra = RecommendationActionabilityEvaluator(session)
    result = ra.evaluate(analysis_run.id)
    assert result["recommendation_actionability_score"] == 1.0
    assert result["has_recommended_motion"] is True
    assert result["has_next_step"] is True
    assert result["has_technical_experiment"] is True
    assert result["has_success_metrics"] is True


def test_degraded_state_evaluator_no_run(session: Session) -> None:
    ds = DegradedStateEvaluator(session)
    result = ds.evaluate("nonexistent")
    assert result["degraded_state_count"] == 0


def test_degraded_state_evaluator_with_checks(
    session: Session,
    startup: Startup,
    analysis_run: AnalysisRun,
) -> None:
    session.add_all(
        [
            ProductReadinessCheck(
                id="rc-1",
                analysis_run_id=analysis_run.id,
                code="TEST_CHECK",
                severity="warning",
                status="degraded",
                user_message="Test degraded",
                internal_detail="Detail",
                recommended_action="Fix it",
                metadata_json={},
                observed_at=datetime.now(UTC),
            ),
            ProductReadinessCheck(
                id="rc-2",
                analysis_run_id=analysis_run.id,
                code="TEST_ERROR",
                severity="error",
                status="error",
                user_message="Test error",
                internal_detail="Detail",
                recommended_action="Fix it",
                metadata_json={},
                observed_at=datetime.now(UTC),
            ),
            ProductReadinessCheck(
                id="rc-3",
                analysis_run_id=analysis_run.id,
                code="TEST_OK",
                severity="info",
                status="ok",
                user_message="All good",
                internal_detail="Detail",
                recommended_action="",
                metadata_json={},
                observed_at=datetime.now(UTC),
            ),
        ]
    )
    session.flush()

    ds = DegradedStateEvaluator(session)
    result = ds.evaluate(analysis_run.id)
    assert result["degraded_state_count"] == 2


def test_export_readiness_evaluator_no_dossier(session: Session) -> None:
    er = ExportReadinessEvaluator(session)
    result = er.evaluate("nonexistent")
    assert result["dossier_exists"] is False
    assert result["export_readiness_score"] == 0.0


def test_export_readiness_evaluator_full(
    session: Session,
    startup: Startup,
    analysis_run: AnalysisRun,
) -> None:
    session.add(
        ActivationDossierRecord(
            id="dossier-export",
            analysis_run_id=analysis_run.id,
            version=1,
            schema_version="1.0",
            dossier_json={"startup": {"name": "Test"}},
            dossier_markdown="# Full markdown",
            is_latest=True,
            evidence_coverage=1.0,
            unsupported_claim_count=0,
            recommended_motion="poc",
        )
    )
    session.flush()

    er = ExportReadinessEvaluator(session)
    result = er.evaluate(analysis_run.id)
    assert result["dossier_exists"] is True
    assert result["export_readiness_score"] > 0.0
    assert result["export_readiness_score"] <= 1.0


def test_review_readiness_evaluator_no_run(session: Session) -> None:
    rr = ReviewReadinessEvaluator(session)
    result = rr.evaluate("nonexistent")
    assert result["review_readiness_score"] == 0.0
    assert result["has_review"] is False


def test_review_readiness_evaluator_with_review(
    session: Session,
    startup: Startup,
    analysis_run: AnalysisRun,
) -> None:
    session.add(
        ReviewDecision(
            id="review-1",
            analysis_run_id=analysis_run.id,
            startup_id=startup.id,
            decision="approve",
            reviewer="Test Reviewer",
            notes="Looks good",
            metadata_json={},
        )
    )
    session.flush()

    rr = ReviewReadinessEvaluator(session)
    result = rr.evaluate(analysis_run.id)
    assert result["has_review"] is True
    assert result["review_readiness_score"] > 0.0
