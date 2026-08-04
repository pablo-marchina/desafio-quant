from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.product import ProductRepository


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'repo.db').as_posix()}")
    session = runtime.session_factory()
    yield ProductRepository(session)
    session.close()
    reset_product_database_runtime()


def _create_startup(repository: ProductRepository, name: str = "Radar AI") -> str:
    startup = repository.create_startup(
        name=name,
        website="https://radar.example.com",
        country="Brazil",
        sector="Enterprise AI",
        description="AI platform",
        product_summary="Production AI intelligence",
        tags=["ai-native"],
    )
    repository.session.commit()
    return startup.id


def test_startup_repository_crud_and_unique_normalized_name(
    repository: ProductRepository,
) -> None:
    startup_id = _create_startup(repository)
    repository.add_evidence(
        startup_id=startup_id,
        claim="Runs AI workloads in production",
        source_url="https://radar.example.com/technology",
        source_type="official_site",
        quote_or_evidence="The platform runs machine learning workloads in production.",
        confidence="high",
        collected_at=datetime.now(UTC),
    )
    repository.session.commit()

    startup = repository.get_startup(startup_id)
    assert startup is not None
    assert startup.normalized_name == "radar ai"
    assert len(startup.evidence) == 1

    updated = repository.update_startup(startup_id, sector="AI Infrastructure")
    repository.session.commit()
    assert updated is not None
    assert updated.sector == "AI Infrastructure"

    with pytest.raises(IntegrityError):
        repository.create_startup(
            name="  RADAR   AI ",
            website="https://other.example.com",
            country="Brazil",
            sector="AI",
            description="Duplicate",
            product_summary="Duplicate",
        )
    repository.session.rollback()


def test_analysis_run_brief_and_readiness_repository(repository: ProductRepository) -> None:
    startup_id = _create_startup(repository)
    run = repository.create_analysis_run(
        startup_id=startup_id,
        input_snapshot={"startup_id": startup_id},
        pipeline_version="test",
        corpus_version="v1",
        config_snapshot={"use_rag": False},
    )
    repository.update_analysis_run_status(
        run.id,
        status="running",
        started_at=datetime.now(UTC),
    )
    repository.save_score(
        analysis_run_id=run.id,
        score_type="composite",
        value=42.0,
        confidence="medium",
        components={"composite_score": 42.0},
        missing_evidence=[],
    )
    repository.save_action_brief(
        analysis_run_id=run.id,
        version=1,
        schema_version="2.0",
        brief_json={"startup_name": "Radar AI"},
        brief_markdown="# Radar AI",
    )
    repository.save_readiness_check(
        analysis_run_id=run.id,
        code="MISSING_EVIDENCE",
        severity="warning",
        status="degraded",
        user_message="Missing evidence.",
        internal_detail="One item missing.",
        recommended_action="Collect evidence.",
    )
    repository.update_analysis_run_status(
        run.id,
        status="degraded",
        completed_at=datetime.now(UTC),
        degraded_reason="MISSING_EVIDENCE",
    )
    repository.session.commit()

    loaded = repository.get_analysis_run(run.id)
    assert loaded is not None
    assert loaded.status == "degraded"
    assert loaded.scores[0].score_type == "composite"
    assert loaded.briefs[0].is_latest is True
    assert loaded.readiness_checks[0].code == "MISSING_EVIDENCE"
    assert repository.get_latest_analysis_run(startup_id).id == run.id


def test_update_startup_fields_partial(repository: ProductRepository) -> None:
    startup_id = _create_startup(repository)

    updated = repository.update_startup_fields(startup_id, {"sector": "AI Infrastructure"})
    repository.session.commit()
    assert updated is not None
    assert updated.sector == "AI Infrastructure"
    assert updated.name == "Radar AI"

    updated2 = repository.update_startup_fields(startup_id, {"name": "Radar AI 2.0"})
    assert updated2 is not None
    assert updated2.normalized_name == "radar ai 2.0"


def test_update_startup_fields_does_not_delete_evidence(repository: ProductRepository) -> None:
    startup_id = _create_startup(repository)
    repository.add_evidence(
        startup_id=startup_id,
        claim="Original claim",
        source_url="https://example.com/evidence",
        source_type="official_site",
        quote_or_evidence="Quote",
        confidence="high",
        collected_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    repository.session.commit()

    repository.update_startup_fields(startup_id, {"sector": "New Sector"})
    repository.session.commit()

    startup = repository.get_startup(startup_id)
    assert startup is not None
    assert len(startup.evidence) == 1


def test_action_brief_versioning_marks_only_latest(repository: ProductRepository) -> None:
    startup_id = _create_startup(repository)
    run = repository.create_analysis_run(
        startup_id=startup_id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    repository.save_action_brief(
        analysis_run_id=run.id,
        version=1,
        schema_version="2.0",
        brief_json={"version": 1},
        brief_markdown="# v1",
    )
    latest = repository.save_action_brief(
        analysis_run_id=run.id,
        version=2,
        schema_version="2.0",
        brief_json={"version": 2},
        brief_markdown="# v2",
    )
    repository.session.commit()

    loaded = repository.get_analysis_run(run.id)
    assert loaded is not None
    assert sum(brief.is_latest for brief in loaded.briefs) == 1
    assert repository.get_latest_action_brief(run.id).id == latest.id
