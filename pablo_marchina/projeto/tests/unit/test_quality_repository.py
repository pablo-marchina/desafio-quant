from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.database.models import ProductQualityMetric
from src.database.session import configure_product_database, reset_product_database_runtime
from src.quality.repository import ProductQualityRepository


@pytest.fixture
def session(tmp_path: Path) -> Session:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'quality_repo.db').as_posix()}")
    sess = runtime.session_factory()
    yield sess
    sess.close()
    reset_product_database_runtime()


@pytest.fixture
def repository(session: Session) -> ProductQualityRepository:
    return ProductQualityRepository(session)


def test_create_and_complete_quality_run(  # noqa: E501
    repository: ProductQualityRepository,
    session: Session,
) -> None:
    run = repository.create_quality_run(analysis_run_id="run-1")
    session.flush()
    assert run.id is not None
    assert run.status == "running"
    assert run.analysis_run_id == "run-1"
    assert run.evaluator_version == "1.0"

    completed = repository.complete_quality_run(run.id)
    session.flush()
    assert completed is not None
    assert completed.status == "completed"
    assert completed.completed_at is not None


def test_create_and_fail_quality_run(  # noqa: E501
    repository: ProductQualityRepository,
    session: Session,
) -> None:
    run = repository.create_quality_run(analysis_run_id="run-2")
    session.flush()

    failed = repository.fail_quality_run(run.id, degraded_reason="test failure")
    session.flush()
    assert failed is not None
    assert failed.status == "failed"
    assert failed.degraded_reason == "test failure"


def test_create_and_degrade_quality_run(  # noqa: E501
    repository: ProductQualityRepository,
    session: Session,
) -> None:
    run = repository.create_quality_run(analysis_run_id="run-3")
    session.flush()

    degraded = repository.degrade_quality_run(run.id, degraded_reason="low quality")
    session.flush()
    assert degraded is not None
    assert degraded.status == "degraded"
    assert degraded.degraded_reason == "low quality"


def test_add_metric(repository: ProductQualityRepository, session: Session) -> None:
    run = repository.create_quality_run(analysis_run_id="run-4")
    session.flush()

    metric = ProductQualityMetric(
        quality_run_id=run.id,
        metric_name="test_metric",
        metric_value=0.85,
        threshold=0.70,
        passed=True,
        severity="warn",
    )
    saved = repository.add_metric(metric)
    session.flush()
    assert saved.id is not None
    assert saved.metric_name == "test_metric"
    assert saved.metric_value == 0.85


def test_add_metrics_bulk(repository: ProductQualityRepository, session: Session) -> None:
    run = repository.create_quality_run(analysis_run_id="run-5")
    session.flush()

    metrics = [
        ProductQualityMetric(
            quality_run_id=run.id,
            metric_name=f"metric_{i}",
            metric_value=float(i),
            threshold=0.5,
            passed=True,
            severity="info",
        )
        for i in range(3)
    ]
    saved = repository.add_metrics_bulk(metrics)
    session.flush()
    assert len(saved) == 3

    loaded = repository.get_metrics_for_quality_run(run.id)
    assert len(loaded) == 3


def test_list_quality_runs_for_analysis(  # noqa: E501
    repository: ProductQualityRepository,
    session: Session,
) -> None:
    repository.create_quality_run(analysis_run_id="run-list-1")
    repository.create_quality_run(analysis_run_id="run-list-1")
    repository.create_quality_run(analysis_run_id="run-list-2")
    session.flush()

    runs = repository.list_quality_runs_for_analysis_run("run-list-1")
    assert len(runs) == 2

    runs2 = repository.list_quality_runs_for_analysis_run("run-list-2")
    assert len(runs2) == 1


def test_get_latest_quality_run(repository: ProductQualityRepository, session: Session) -> None:
    repository.create_quality_run(analysis_run_id="run-latest")
    session.flush()
    r2 = repository.create_quality_run(analysis_run_id="run-latest")
    session.flush()

    latest = repository.get_latest_quality_run_for_analysis_run("run-latest")
    assert latest is not None
    assert latest.id == r2.id


def test_delete_quality_runs(repository: ProductQualityRepository, session: Session) -> None:
    repository.create_quality_run(analysis_run_id="run-del")
    repository.create_quality_run(analysis_run_id="run-del")
    session.flush()

    count = repository.delete_quality_runs_for_analysis_run("run-del")
    assert count == 2

    remaining = repository.list_quality_runs_for_analysis_run("run-del")
    assert len(remaining) == 0


def test_get_quality_run_not_found(repository: ProductQualityRepository) -> None:
    assert repository.get_quality_run("nonexistent") is None


def test_complete_nonexistent_run(repository: ProductQualityRepository) -> None:
    assert repository.complete_quality_run("nonexistent") is None


def test_fail_nonexistent_run(repository: ProductQualityRepository) -> None:
    assert repository.fail_quality_run("nonexistent") is None


def test_degrade_nonexistent_run(repository: ProductQualityRepository) -> None:
    assert repository.degrade_quality_run("nonexistent") is None
