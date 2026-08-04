"""Testes das transicoes de estado da entidade AnalysisJob."""

from uuid import uuid4

import pytest

from apps.api.src.modules.orchestration.domain.entities import AnalysisJob
from apps.api.src.modules.orchestration.domain.enums import AnalysisJobStatus
from apps.api.src.modules.orchestration.domain.exceptions import (
    InvalidAnalysisJobTransitionError,
)


def test_new_job_starts_pending() -> None:
    job = AnalysisJob(startup_id=uuid4())

    assert job.status is AnalysisJobStatus.PENDING
    assert job.started_at is None


def test_start_transitions_to_running() -> None:
    job = AnalysisJob(startup_id=uuid4())

    job.start()

    assert job.status is AnalysisJobStatus.RUNNING
    assert job.started_at is not None


def test_start_twice_raises() -> None:
    job = AnalysisJob(startup_id=uuid4())
    job.start()

    with pytest.raises(InvalidAnalysisJobTransitionError):
        job.start()


def test_complete_transitions_to_completed_with_result() -> None:
    job = AnalysisJob(startup_id=uuid4())
    job.start()
    briefing_id = uuid4()

    job.complete(recommendation_count=3, briefing_id=briefing_id)

    assert job.status is AnalysisJobStatus.COMPLETED
    assert job.recommendation_count == 3
    assert job.briefing_id == briefing_id
    assert job.finished_at is not None


def test_complete_without_starting_raises() -> None:
    job = AnalysisJob(startup_id=uuid4())

    with pytest.raises(InvalidAnalysisJobTransitionError):
        job.complete(recommendation_count=0, briefing_id=uuid4())


def test_fail_transitions_to_failed_with_reason() -> None:
    job = AnalysisJob(startup_id=uuid4())
    job.start()

    job.fail("Startup nao encontrada.")

    assert job.status is AnalysisJobStatus.FAILED
    assert job.error_message == "Startup nao encontrada."
    assert job.finished_at is not None


def test_fail_without_starting_raises() -> None:
    job = AnalysisJob(startup_id=uuid4())

    with pytest.raises(InvalidAnalysisJobTransitionError):
        job.fail("erro")
