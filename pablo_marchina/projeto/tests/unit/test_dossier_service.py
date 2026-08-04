from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.claim import ClaimRepository
from src.repositories.product import ProductRepository
from src.repositories.review import ReviewDecisionRepository
from src.services.product.dossier_service import ActivationDossierService


@pytest.fixture
def repo_session(tmp_path: Path):
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'dossier_svc.db').as_posix()}")
    session = runtime.session_factory()
    yield session
    session.close()
    reset_product_database_runtime()


def _create_minimal_run(session) -> str:
    pr = ProductRepository(session)
    startup = pr.create_startup(
        name="Dossier Svc Test",
        website="https://svc-test.example.com",
        country="Brazil",
        sector="Enterprise AI",
        description="Test description",
        product_summary="Test startup for dossier service",
    )
    pr.add_evidence(
        startup_id=startup.id,
        claim="Uses AI in production",
        source_url="https://svc-test.example.com",
        source_type="official_site",
        quote_or_evidence="AI production usage",
        confidence="high",
        collected_at=datetime.now(UTC),
    )
    pr.session.commit()

    run = pr.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={"startup": {"name": "Dossier Svc Test"}},
        pipeline_version="test",
        corpus_version="v1",
        config_snapshot={},
    )
    pr.update_analysis_run_status(
        run.id,
        status="completed",
        completed_at=datetime.now(UTC),
        output_snapshot={
            "recommended_motion": "architecture_review",
            "missing_evidence": ["funding rounds"],
            "composite_score": {"composite_score": 72, "confidence": "medium"},
        },
    )
    pr.save_score(
        analysis_run_id=run.id,
        score_type="defensibility",
        value=65.0,
        confidence="medium",
        components={"score": 65.0},
        missing_evidence=[],
    )
    pr.save_score(
        analysis_run_id=run.id,
        score_type="inception_fit",
        value=78.0,
        confidence="high",
        components={"score": 78.0},
        missing_evidence=[],
    )
    pr.save_score(
        analysis_run_id=run.id,
        score_type="production_readiness",
        value=55.0,
        confidence="medium",
        components={"score": 55.0},
        missing_evidence=[],
    )
    pr.save_score(
        analysis_run_id=run.id,
        score_type="composite",
        value=72.0,
        confidence="medium",
        components={"composite_score": 72.0},
        missing_evidence=[],
    )
    pr.save_gap(
        analysis_run_id=run.id,
        gap_type="high_latency",
        detected=True,
        confidence="high",
        evidence_tag="inference_claim",
        reasoning="Model serving latency is high according to evidence",
        evidence_refs=[{"claim": "Slow inference", "source_url": "https://example.com"}],
    )
    pr.save_gap(
        analysis_run_id=run.id,
        gap_type="data_privacy_gap",
        detected=False,
        confidence="low",
        evidence_tag="unverified",
        reasoning="No evidence available",
        evidence_refs=[],
    )
    pr.save_mapping(
        analysis_run_id=run.id,
        gap_record_id=None,
        technology_name="TensorRT",
        addresses_gap="high_latency",
        justification="TensorRT optimizes inference latency",
        recommendation_action="approach_now",
        priority="high",
        details={},
    )

    pr.save_action_brief(
        analysis_run_id=run.id,
        version=1,
        schema_version="2.0",
        brief_json={
            "startup_name": "Dossier Svc Test",
            "sections": [{"title": "Executive Summary", "content": "Promising startup."}],
        },
        brief_markdown="# Action Brief",
    )
    pr.save_readiness_check(
        analysis_run_id=run.id,
        code="MISSING_EVIDENCE",
        severity="warning",
        status="degraded",
        user_message="Missing evidence for funding rounds.",
        internal_detail="No evidence found for funding",
        recommended_action="Collect funding evidence.",
    )

    pr.session.commit()
    return run.id


def test_build_dossier_minimal_run(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    record = svc.build_dossier_for_analysis_run(run_id)
    assert record is not None
    assert record.version == 1
    assert record.is_latest is True
    assert record.schema_version == "1.0"
    assert record.recommended_motion == "architecture_review"

    dossier = record.dossier_json
    assert dossier["metadata"]["analysis_run_id"] == run_id
    assert dossier["startup"]["name"] == "Dossier Svc Test"
    assert dossier["executive_verdict"]["recommended_motion"] == "architecture_review"
    assert dossier["executive_verdict"]["evidence_coverage"] >= 0.0
    assert dossier["scores"]["defensibility_score"]["value"] == 65.0
    assert dossier["scores"]["inception_fit_score"]["value"] == 78.0
    assert dossier["scores"]["production_readiness_score"]["value"] == 55.0
    assert dossier["scores"]["composite_score"] == 72.0

    gaps = dossier["gaps"]["detected_gaps"]
    assert len(gaps) >= 1
    assert any(g["gap_type"] == "high_latency" for g in gaps)

    techs = dossier["nvidia_mappings"]["technologies"]
    assert "TensorRT" in techs


def test_build_dossier_twice_returns_existing(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    v1 = svc.build_dossier_for_analysis_run(run_id)
    v2 = svc.build_dossier_for_analysis_run(run_id)
    assert v1.id == v2.id
    assert v1.version == 1
    assert v2.version == 1


def test_regenerate_dossier_creates_new_version(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    v1 = svc.build_dossier_for_analysis_run(run_id)
    assert v1.version == 1
    v2 = svc.regenerate_dossier(run_id)
    assert v2.version == 2
    assert v2.is_latest is True
    v1_again = svc.dossier_repo.get_by_id(v1.id)
    assert v1_again.is_latest is False


def test_get_latest_dossier(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    assert svc.get_latest_dossier(run_id) is None
    svc.build_dossier_for_analysis_run(run_id)
    assert svc.get_latest_dossier(run_id) is not None


def test_get_dossier_markdown(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    assert svc.get_dossier_markdown(run_id) is None
    svc.build_dossier_for_analysis_run(run_id)
    md = svc.get_dossier_markdown(run_id)
    assert md is not None
    assert "# Startup Activation Dossier" in md
    assert "## Executive Verdict" in md
    assert "## Startup Profile" in md
    assert "## Evidence Summary" in md
    assert "## Scores" in md
    assert "## Gap Diagnosis" in md
    assert "## NVIDIA Fit" in md
    assert "## Risks" in md
    assert "## Uncertainties" in md
    assert "## Human Review" in md
    assert "## Recommended Next Step" in md


def test_unsupported_claims_appear_in_risks(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    startup_id = _get_startup_id(repo_session, run_id)
    cr = ClaimRepository(repo_session)
    cr.create_claim(
        startup_id=startup_id,
        analysis_run_id=run_id,
        claim_text="Startup has no competitive moat",
        claim_type="defensibility_claim",
        support_level="unsupported",
    )
    repo_session.commit()
    cov = cr.get_evidence_coverage_summary(run_id)
    assert cov["unsupported_claims"] > 0, f"Expected unsupported claims > 0, got {cov}"
    svc = ActivationDossierService(repo_session)
    record = svc.build_dossier_for_analysis_run(run_id, force_new_version=True)
    dossier = record.dossier_json
    assert (
        dossier["executive_verdict"]["unsupported_claim_count"] > 0
    ), f"Expected unsupported_claim_count > 0, got {dossier['executive_verdict']}"
    risks = dossier["risks"]
    assert any("unsupported" in r.get("risk", "").lower() for r in risks), f"Expected unsupported in risks, got {risks}"
    uncertainties = dossier["uncertainties"]
    assert any(
        "lack evidence" in u.get("description", "").lower() for u in uncertainties
    ), f"Expected unsupported claim mention in uncertainties, got {uncertainties}"


def test_missing_review_appears_in_uncertainties(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    record = svc.build_dossier_for_analysis_run(run_id, force_new_version=True)
    uncertainties = record.dossier_json["uncertainties"]
    assert any("no human review" in u.get("description", "").lower() for u in uncertainties)


def test_review_appears_when_exists(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    review_repo = ReviewDecisionRepository(repo_session)
    review_repo.create(
        analysis_run_id=run_id,
        startup_id=_get_startup_id(repo_session, run_id),
        decision="approve",
        reviewer="test_user",
        notes="Looks good",
    )
    repo_session.commit()
    svc = ActivationDossierService(repo_session)
    record = svc.build_dossier_for_analysis_run(run_id, force_new_version=True)
    review = record.dossier_json["review"]
    assert review["has_review"] is True
    assert review["latest_decision"] == "approve"
    assert review["reviewer"] == "test_user"
    assert review["notes"] == "Looks good"


def test_no_playbook_match_uncertainty(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    record = svc.build_dossier_for_analysis_run(run_id, force_new_version=True)
    uncertainties = record.dossier_json["uncertainties"]
    descriptions = (u.get("description", "").lower() for u in uncertainties)
    has_no_playbook = any("no activation playbook" in d for d in descriptions)
    if record.dossier_json["activation_recommendations"]["total"] == 0:
        assert has_no_playbook


def test_dossier_summary(repo_session) -> None:
    run_id = _create_minimal_run(repo_session)
    svc = ActivationDossierService(repo_session)
    summary = svc.get_dossier_summary(run_id)
    assert summary["dossier_available"] is False
    assert summary["dossier_id"] is None

    svc.build_dossier_for_analysis_run(run_id)
    summary = svc.get_dossier_summary(run_id)
    assert summary["dossier_available"] is True
    assert summary["dossier_id"] is not None
    assert summary["dossier_version"] == 1


def _get_startup_id(session, run_id) -> str:
    from src.database.models import AnalysisRun

    run = session.get(AnalysisRun, run_id)
    return run.startup_id if run else ""
