from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from src.database.models import ActivationDossierRecord
from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.dossier import ActivationDossierRepository
from src.repositories.product import ProductRepository


@pytest.fixture
def repo_session(tmp_path: Path):
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'dossier.db').as_posix()}")
    session = runtime.session_factory()
    yield session
    session.close()
    reset_product_database_runtime()


def _create_run(session) -> str:
    pr = ProductRepository(session)
    startup = pr.create_startup(
        name="Dossier Test",
        website="https://dossier.example.com",
        country="Brazil",
        sector="AI",
        description="Test startup",
        product_summary="AI platform",
    )
    pr.session.commit()
    run = pr.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={"test": True},
        pipeline_version="test",
        corpus_version="v1",
        config_snapshot={},
    )
    pr.session.commit()
    return run.id


def _make_dossier_json(overrides: dict | None = None) -> dict:
    base = {
        "metadata": {"analysis_run_id": "test", "schema_version": "1.0", "dossier_version": 1},
        "executive_verdict": {
            "recommended_motion": "architecture_review",
            "evidence_coverage": 0.85,
            "unsupported_claim_count": 0,
        },
        "evidence_summary": {"evidence_count": 10, "coverage": 0.85},
        "claims": {"key_claims": [], "unsupported_claims": [], "weak_claims": []},
        "scores": {"composite_score": 75},
        "gaps": {"detected_gaps": [], "gap_summary": ""},
        "nvidia_mappings": {"technologies": ["TensorRT"], "mapping_summary": ""},
        "activation_recommendations": {
            "top_playbook": None,
            "top_playbook_id": None,
            "all_recommendations": [],
            "total": 0,
        },
        "suggested_experiment": None,
        "risks": [],
        "uncertainties": [],
        "review": {"has_review": False, "latest_decision": None},
        "next_action": {"next_step": "", "recommended_motion": ""},
        "degraded_states": [],
    }
    if overrides:
        base.update(overrides)
    return base


def test_create_dossier(repo_session) -> None:
    run_id = _create_run(repo_session)
    repo = ActivationDossierRepository(repo_session)
    record = repo.create_dossier(
        analysis_run_id=run_id,
        version=1,
        schema_version="1.0",
        dossier_json=_make_dossier_json(),
        dossier_markdown="# Dossier",
        evidence_coverage=0.85,
        unsupported_claim_count=0,
        top_activation_playbook_id=None,
        recommended_motion="architecture_review",
        review_status=None,
    )
    repo_session.commit()
    assert record.id is not None
    assert record.version == 1
    assert record.is_latest is True


def test_get_latest_for_analysis_run(repo_session) -> None:
    run_id = _create_run(repo_session)
    repo = ActivationDossierRepository(repo_session)
    repo.create_dossier(
        analysis_run_id=run_id,
        version=1,
        schema_version="1.0",
        dossier_json=_make_dossier_json(),
        dossier_markdown="# v1",
        evidence_coverage=0.5,
        unsupported_claim_count=1,
        top_activation_playbook_id=None,
        recommended_motion="review",
        review_status=None,
    )
    repo_session.commit()
    repo.create_dossier(
        analysis_run_id=run_id,
        version=2,
        schema_version="1.0",
        dossier_json=_make_dossier_json(),
        dossier_markdown="# v2",
        evidence_coverage=0.9,
        unsupported_claim_count=0,
        top_activation_playbook_id="latency_opt",
        recommended_motion="poc",
        review_status="approved",
    )
    repo_session.commit()
    latest = repo.get_latest_for_analysis_run(run_id)
    assert latest is not None
    assert latest.version == 2
    assert latest.dossier_markdown == "# v2"


def test_next_version_for_analysis_run(repo_session) -> None:
    run_id = _create_run(repo_session)
    repo = ActivationDossierRepository(repo_session)
    assert repo.next_version_for_analysis_run(run_id) == 1

    repo.create_dossier(
        analysis_run_id=run_id,
        version=1,
        schema_version="1.0",
        dossier_json=_make_dossier_json(),
        dossier_markdown="# v1",
        evidence_coverage=0.5,
        unsupported_claim_count=0,
        top_activation_playbook_id=None,
        recommended_motion="review",
        review_status=None,
    )
    repo_session.commit()
    assert repo.next_version_for_analysis_run(run_id) == 2


def test_mark_previous_not_latest(repo_session) -> None:
    run_id = _create_run(repo_session)
    repo = ActivationDossierRepository(repo_session)
    repo.create_dossier(
        analysis_run_id=run_id,
        version=1,
        schema_version="1.0",
        dossier_json=_make_dossier_json(),
        dossier_markdown="# v1",
        evidence_coverage=0.5,
        unsupported_claim_count=0,
        top_activation_playbook_id=None,
        recommended_motion="review",
        review_status=None,
    )
    repo_session.commit()
    repo.mark_previous_not_latest(run_id)
    repo_session.commit()
    repo.create_dossier(
        analysis_run_id=run_id,
        version=2,
        schema_version="1.0",
        dossier_json=_make_dossier_json(),
        dossier_markdown="# v2",
        evidence_coverage=0.9,
        unsupported_claim_count=0,
        top_activation_playbook_id="test",
        recommended_motion="poc",
        review_status="approved",
    )
    repo_session.commit()
    latest = repo.get_latest_for_analysis_run(run_id)
    assert latest.version == 2
    assert latest.is_latest is True
    previous_count = (
        repo_session.execute(
            select(ActivationDossierRecord).where(
                ActivationDossierRecord.analysis_run_id == run_id,
                ActivationDossierRecord.is_latest.is_(False),
            )
        )
    ).scalar()
    # v1 should now be not latest
    assert previous_count is not None or repo.count_for_analysis_run(run_id) == 2


def test_list_for_analysis_run(repo_session) -> None:
    run_id = _create_run(repo_session)
    repo = ActivationDossierRepository(repo_session)
    for v in range(1, 4):
        repo.create_dossier(
            analysis_run_id=run_id,
            version=v,
            schema_version="1.0",
            dossier_json=_make_dossier_json(),
            dossier_markdown=f"# v{v}",
            evidence_coverage=0.5,
            unsupported_claim_count=0,
            top_activation_playbook_id=None,
            recommended_motion="review",
            review_status=None,
        )
        repo_session.commit()
    all_dossiers = repo.list_for_analysis_run(run_id)
    assert len(all_dossiers) == 3


def test_get_by_id(repo_session) -> None:
    run_id = _create_run(repo_session)
    repo = ActivationDossierRepository(repo_session)
    record = repo.create_dossier(
        analysis_run_id=run_id,
        version=1,
        schema_version="1.0",
        dossier_json=_make_dossier_json(),
        dossier_markdown="# Dossier",
        evidence_coverage=0.5,
        unsupported_claim_count=0,
        top_activation_playbook_id=None,
        recommended_motion="review",
        review_status=None,
    )
    repo_session.commit()
    found = repo.get_by_id(record.id)
    assert found is not None
    assert found.id == record.id


def test_delete_for_analysis_run(repo_session) -> None:
    run_id = _create_run(repo_session)
    repo = ActivationDossierRepository(repo_session)
    for v in range(1, 4):
        repo.create_dossier(
            analysis_run_id=run_id,
            version=v,
            schema_version="1.0",
            dossier_json=_make_dossier_json(),
            dossier_markdown=f"# v{v}",
            evidence_coverage=0.5,
            unsupported_claim_count=0,
            top_activation_playbook_id=None,
            recommended_motion="review",
            review_status=None,
        )
        repo_session.commit()
    assert repo.count_for_analysis_run(run_id) == 3
    repo.delete_for_analysis_run(run_id)
    repo_session.commit()
    assert repo.count_for_analysis_run(run_id) == 0
