"""Testes das entidades do domínio de ingestion."""

from uuid import uuid4

import pytest

from apps.api.src.modules.ingestion.domain.entities import IngestionJob
from apps.api.src.modules.ingestion.domain.enums import (
    DocumentSourceType,
    IngestionJobStatus,
)
from apps.api.src.modules.ingestion.domain.exceptions import (
    InvalidIngestionJobTransitionError,
)


def _make_job() -> IngestionJob:
    return IngestionJob(scraping_result_id=uuid4())


def test_job_starts_from_pending() -> None:
    job = _make_job()
    job.start()
    assert job.status is IngestionJobStatus.RUNNING
    assert job.started_at is not None


def test_job_source_type_defaults_to_startup_evidence() -> None:
    job = _make_job()
    assert job.source_type is DocumentSourceType.STARTUP_EVIDENCE


def test_job_accepts_nvidia_knowledge_source_type() -> None:
    job = IngestionJob(
        scraping_result_id=uuid4(),
        source_type=DocumentSourceType.NVIDIA_KNOWLEDGE,
    )
    assert job.source_type is DocumentSourceType.NVIDIA_KNOWLEDGE


def test_job_cannot_start_from_running() -> None:
    job = _make_job()
    job.start()
    with pytest.raises(InvalidIngestionJobTransitionError):
        job.start()


def test_job_completes_with_document_id() -> None:
    job = _make_job()
    doc_id = uuid4()
    job.start()
    job.complete(doc_id)
    assert job.status is IngestionJobStatus.COMPLETED
    assert job.document_id == doc_id
    assert job.finished_at is not None


def test_job_fails_from_running() -> None:
    job = _make_job()
    job.start()
    job.fail("algo deu errado")
    assert job.status is IngestionJobStatus.FAILED
    assert job.error_message == "algo deu errado"
    assert job.finished_at is not None


def test_job_cannot_complete_from_pending() -> None:
    job = _make_job()
    with pytest.raises(InvalidIngestionJobTransitionError):
        job.complete(uuid4())


def test_job_cannot_fail_from_pending() -> None:
    job = _make_job()
    with pytest.raises(InvalidIngestionJobTransitionError):
        job.fail("erro")


def test_job_fail_dispatch_from_pending() -> None:
    job = _make_job()
    job.fail_dispatch("redis indisponivel")
    assert job.status is IngestionJobStatus.FAILED
    assert "redis" in job.error_message


def test_job_fail_dispatch_requires_pending() -> None:
    job = _make_job()
    job.start()
    with pytest.raises(InvalidIngestionJobTransitionError):
        job.fail_dispatch("tarde demais")
