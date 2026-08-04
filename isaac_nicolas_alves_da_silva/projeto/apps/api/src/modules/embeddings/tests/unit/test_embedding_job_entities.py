"""Testes das entidades EmbeddingJob e EmbeddingJobChunk."""

from uuid import uuid4

import pytest

from apps.api.src.modules.embeddings.domain.entities import (
    MAX_CHUNK_ATTEMPTS,
    EmbeddingJob,
    EmbeddingJobChunk,
    chunk_content_hash,
    estimate_input_tokens,
)
from apps.api.src.modules.embeddings.domain.enums import (
    EmbeddingJobChunkStatus,
    EmbeddingJobStatus,
)
from apps.api.src.modules.embeddings.domain.exceptions import (
    InvalidEmbeddingJobTransitionError,
)


# ---------------------------------------------------------------------------
# EmbeddingJob
# ---------------------------------------------------------------------------


def test_start_transitions_pending_to_running() -> None:
    job = EmbeddingJob(document_id=uuid4())

    job.start(total_chunks=5)

    assert job.status is EmbeddingJobStatus.RUNNING
    assert job.total_chunks == 5
    assert job.started_at is not None


def test_start_raises_when_not_pending() -> None:
    job = EmbeddingJob(document_id=uuid4())
    job.start(total_chunks=1)

    with pytest.raises(InvalidEmbeddingJobTransitionError):
        job.start(total_chunks=1)


def test_fail_from_pending() -> None:
    job = EmbeddingJob(document_id=uuid4())

    job.fail("documento sem chunks")

    assert job.status is EmbeddingJobStatus.FAILED
    assert job.error_message == "documento sem chunks"
    assert job.finished_at is not None


def test_fail_from_running() -> None:
    job = EmbeddingJob(document_id=uuid4())
    job.start(total_chunks=1)

    job.fail("erro generico")

    assert job.status is EmbeddingJobStatus.FAILED


def test_fail_raises_when_already_finished() -> None:
    job = EmbeddingJob(document_id=uuid4())
    job.fail("primeira falha")

    with pytest.raises(InvalidEmbeddingJobTransitionError):
        job.fail("segunda falha")


def test_finish_completed_when_no_failures() -> None:
    job = EmbeddingJob(document_id=uuid4())
    job.start(total_chunks=3)

    job.finish(succeeded=3, failed=0)

    assert job.status is EmbeddingJobStatus.COMPLETED
    assert job.finished_at is not None


def test_finish_failed_when_no_successes() -> None:
    job = EmbeddingJob(document_id=uuid4())
    job.start(total_chunks=3)

    job.finish(succeeded=0, failed=3, error_message="todos falharam")

    assert job.status is EmbeddingJobStatus.FAILED
    assert job.error_message == "todos falharam"


def test_finish_partial_when_mixed_results() -> None:
    job = EmbeddingJob(document_id=uuid4())
    job.start(total_chunks=3)

    job.finish(succeeded=2, failed=1)

    assert job.status is EmbeddingJobStatus.PARTIAL


def test_finish_raises_when_not_running() -> None:
    job = EmbeddingJob(document_id=uuid4())

    with pytest.raises(InvalidEmbeddingJobTransitionError):
        job.finish(succeeded=1, failed=0)


# ---------------------------------------------------------------------------
# EmbeddingJobChunk
# ---------------------------------------------------------------------------


def test_complete_marks_chunk_completed_and_clears_error() -> None:
    chunk = EmbeddingJobChunk(job_id=uuid4(), chunk_id=uuid4())
    chunk.record_failure("falha temporaria")

    chunk.complete(
        model_name="fake-model",
        vector_dimension=2,
        input_char_count=11,
        estimated_input_tokens=3,
        latency_ms=12,
        content_hash="abc123",
    )

    assert chunk.status is EmbeddingJobChunkStatus.COMPLETED
    assert chunk.error_message is None
    assert chunk.finished_at is not None
    assert chunk.model_name == "fake-model"
    assert chunk.vector_dimension == 2
    assert chunk.input_char_count == 11
    assert chunk.estimated_input_tokens == 3
    assert chunk.latency_ms == 12
    assert chunk.content_hash == "abc123"


def test_job_records_aggregate_metrics_from_chunks() -> None:
    job = EmbeddingJob(document_id=uuid4())
    first = EmbeddingJobChunk(job_id=job.id, chunk_id=uuid4())
    second = EmbeddingJobChunk(job_id=job.id, chunk_id=uuid4())
    first.complete(
        model_name="fake-model",
        vector_dimension=2,
        input_char_count=10,
        estimated_input_tokens=3,
        latency_ms=7,
        content_hash="first",
    )
    second.complete(
        model_name="fake-model",
        vector_dimension=2,
        input_char_count=20,
        estimated_input_tokens=5,
        latency_ms=13,
        content_hash="second",
    )

    job.record_metrics_from_chunks([first, second])

    assert job.total_latency_ms == 20
    assert job.total_input_char_count == 30
    assert job.total_estimated_input_tokens == 8


def test_record_failure_stays_pending_below_attempt_threshold() -> None:
    chunk = EmbeddingJobChunk(job_id=uuid4(), chunk_id=uuid4())

    chunk.record_failure("erro transitorio")

    assert chunk.status is EmbeddingJobChunkStatus.PENDING
    assert chunk.attempt_count == 1
    assert chunk.error_message == "erro transitorio"
    assert chunk.finished_at is None


def test_record_failure_becomes_failed_at_attempt_threshold() -> None:
    chunk = EmbeddingJobChunk(job_id=uuid4(), chunk_id=uuid4())

    for _ in range(MAX_CHUNK_ATTEMPTS):
        chunk.record_failure("erro persistente")

    assert chunk.status is EmbeddingJobChunkStatus.FAILED
    assert chunk.attempt_count == MAX_CHUNK_ATTEMPTS
    assert chunk.finished_at is not None


def test_embedding_metric_helpers_are_deterministic() -> None:
    text = "abcd efgh"

    assert estimate_input_tokens(text) == 3
    assert chunk_content_hash(text) == chunk_content_hash(text)
