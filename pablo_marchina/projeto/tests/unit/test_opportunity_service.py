from __future__ import annotations

from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.product import ProductRepository
from src.services.product.opportunity_service import OpportunityService


@pytest.fixture
def service(tmp_path: Path) -> OpportunityService:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'opp.db').as_posix()}")
    session = runtime.session_factory()
    yield OpportunityService(session)
    session.close()
    reset_product_database_runtime()


def _setup_startup_with_run(repo: ProductRepository, name: str, sector: str, score_value: float) -> str:
    startup = repo.create_startup(
        name=name,
        website=f"https://{name.lower().replace(' ', '')}.example.com",
        country="Brazil",
        sector=sector,
        description=f"{name} description",
        product_summary=f"{name} summary",
    )
    run = repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    from datetime import UTC, datetime

    repo.update_analysis_run_status(
        run.id,
        status="completed",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        output_snapshot={
            "startup_name": name,
            "recommended_motion": "immediate_outreach",
            "composite_score": {"composite_score": score_value, "confidence": "medium"},
        },
    )
    repo.save_score(
        analysis_run_id=run.id,
        score_type="inception_fit",
        value=score_value,
        confidence="medium",
        components={"score": score_value},
        missing_evidence=[],
    )
    repo.save_score(
        analysis_run_id=run.id,
        score_type="defensibility",
        value=score_value * 0.8,
        confidence="medium",
        components={"score": score_value * 0.8},
        missing_evidence=[],
    )
    repo.save_score(
        analysis_run_id=run.id,
        score_type="production_readiness",
        value=score_value * 0.6,
        confidence="medium",
        components={"score": score_value * 0.6},
        missing_evidence=[],
    )
    repo.session.commit()
    return startup.id


def test_opportunity_ranking_returns_sorted_results(
    service: OpportunityService,
) -> None:
    repo = ProductRepository(service.session)
    _setup_startup_with_run(repo, "Alpha AI", "Enterprise AI", 85.0)
    _setup_startup_with_run(repo, "Beta ML", "HealthTech", 45.0)
    _setup_startup_with_run(repo, "Gamma Deep", "FinTech", 70.0)

    items, total = service.list_opportunities(limit=10)
    assert total == 3
    scores = [i["inception_fit_score"] for i in items if i["inception_fit_score"] is not None]
    assert scores == sorted(scores, reverse=True), "Should be sorted descending by inception_fit_score"


def test_opportunity_filters_by_sector(service: OpportunityService) -> None:
    repo = ProductRepository(service.session)
    _setup_startup_with_run(repo, "Alpha AI", "Enterprise AI", 85.0)
    _setup_startup_with_run(repo, "Beta ML", "HealthTech", 45.0)

    items, total = service.list_opportunities(sector="HealthTech")
    assert total == 1
    assert items[0]["startup_name"] == "Beta ML"


def test_opportunity_filters_min_score(service: OpportunityService) -> None:
    repo = ProductRepository(service.session)
    _setup_startup_with_run(repo, "Alpha AI", "Enterprise AI", 80.0)
    _setup_startup_with_run(repo, "Beta ML", "HealthTech", 40.0)

    items, total = service.list_opportunities(min_score=60.0)
    assert total == 1
    assert items[0]["startup_name"] == "Alpha AI"


def test_opportunity_ignores_data_demo_runs(service: OpportunityService) -> None:
    import inspect as ins

    source = ins.getsource(type(service))
    assert "data/demo_runs" not in source


def test_opportunity_empty_when_no_runs(service: OpportunityService) -> None:
    items, total = service.list_opportunities()
    assert items == []
    assert total == 0


def test_opportunity_review_status_present(service: OpportunityService) -> None:
    repo = ProductRepository(service.session)
    sid = _setup_startup_with_run(repo, "Alpha AI", "Enterprise AI", 80.0)

    run = repo.get_latest_analysis_run(sid)
    assert run is not None

    from src.repositories.review import ReviewDecisionRepository

    review_repo = ReviewDecisionRepository(service.session)
    review_repo.create(
        analysis_run_id=run.id,
        startup_id=sid,
        decision="approve",
        reviewer="test",
        notes="Approved",
    )
    service.session.commit()

    items, total = service.list_opportunities()
    assert total == 1
    assert items[0]["review_status"] == "approve"
