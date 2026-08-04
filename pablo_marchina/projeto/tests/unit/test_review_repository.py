from __future__ import annotations

from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.product import ProductRepository
from src.repositories.review import ReviewDecisionRepository


@pytest.fixture
def repos(tmp_path: Path) -> tuple[ReviewDecisionRepository, ProductRepository]:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'review.db').as_posix()}")
    session = runtime.session_factory()
    yield ReviewDecisionRepository(session), ProductRepository(session)
    session.close()
    reset_product_database_runtime()


def _create_startup_and_run(
    product_repo: ProductRepository,
) -> tuple[str, str]:
    startup = product_repo.create_startup(
        name="Review Test",
        website="https://review.example.com",
        country="Brazil",
        sector="AI",
        description="Test startup",
        product_summary="Test summary",
    )
    run = product_repo.create_analysis_run(
        startup_id=startup.id,
        input_snapshot={},
        pipeline_version="test",
        corpus_version=None,
        config_snapshot={},
    )
    product_repo.session.commit()
    return startup.id, run.id


def test_review_create_and_latest(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    r1 = review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="approve",
        reviewer="analyst-1",
        notes="Good startup",
    )
    review_repo.session.commit()
    assert r1.decision == "approve"

    review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="needs_more_evidence",
        reviewer="analyst-2",
        notes="Need more data",
        metadata={"flag": "incomplete"},
    )
    review_repo.session.commit()

    latest = review_repo.get_latest_for_run(run_id)
    assert latest is not None
    assert latest.decision == "needs_more_evidence"

    all_reviews = review_repo.list_for_run(run_id)
    assert len(all_reviews) == 2


def test_review_does_not_recalculate_score(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    product_repo.save_score(
        analysis_run_id=run_id,
        score_type="composite",
        value=42.0,
        confidence="medium",
        components={"composite_score": 42.0},
        missing_evidence=[],
    )
    product_repo.session.commit()

    review_repo.create(
        analysis_run_id=run_id,
        startup_id=startup_id,
        decision="reject",
        reviewer="analyst-1",
        notes="Not a fit",
    )
    review_repo.session.commit()

    run = product_repo.get_analysis_run(run_id)
    assert run is not None
    assert run.scores[0].value == 42.0


def test_review_multiple_decisions_append_only(
    repos: tuple[ReviewDecisionRepository, ProductRepository],
) -> None:
    review_repo, product_repo = repos
    startup_id, run_id = _create_startup_and_run(product_repo)

    decisions = ["approve", "needs_more_evidence", "monitor"]
    for i, dec in enumerate(decisions):
        review_repo.create(
            analysis_run_id=run_id,
            startup_id=startup_id,
            decision=dec,
            reviewer=f"user-{i}",
            notes=f"Review {i}",
        )
    review_repo.session.commit()

    all_reviews = review_repo.list_for_run(run_id)
    assert len(all_reviews) == 3

    latest = review_repo.get_latest_for_run(run_id)
    assert latest is not None
    assert latest.decision == "monitor"
