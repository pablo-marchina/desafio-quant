"""Entidades e value objects do dominio do modulo embeddings."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from apps.api.src.modules.embeddings.domain.enums import (
    EmbeddingJobChunkStatus,
    EmbeddingJobStatus,
)
from apps.api.src.modules.embeddings.domain.exceptions import (
    InvalidEmbeddingDimensionError,
    InvalidEmbeddingJobTransitionError,
)

MAX_CHUNK_ATTEMPTS = 3


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class EmbeddingVector:
    """Vetor de embedding imutavel.

    Nao tem identidade ou ciclo de vida proprio: representa apenas o
    resultado de transformar um texto em um vetor numerico.
    """

    values: tuple[float, ...]
    dimension: int
    model_name: str

    def __post_init__(self) -> None:
        if len(self.values) != self.dimension:
            raise InvalidEmbeddingDimensionError(
                f"Vetor tem {len(self.values)} valores, "
                f"mas dimension declarada e {self.dimension}."
            )


@dataclass
class EmbeddingJob:
    """Processo de gerar o embedding de todos os chunks de um documento."""

    document_id: UUID

    id: UUID = field(default_factory=uuid4)
    status: EmbeddingJobStatus = EmbeddingJobStatus.PENDING
    total_chunks: int = 0
    succeeded_chunks: int = 0
    failed_chunks: int = 0
    total_latency_ms: int = 0
    total_input_char_count: int = 0
    total_estimated_input_tokens: int = 0
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self, *, total_chunks: int) -> None:
        if self.status is not EmbeddingJobStatus.PENDING:
            raise InvalidEmbeddingJobTransitionError(
                f"EmbeddingJob {self.id} nao pode iniciar a partir de {self.status}."
            )
        self.status = EmbeddingJobStatus.RUNNING
        self.total_chunks = total_chunks
        self.started_at = utc_now()

    def fail(self, reason: str) -> None:
        if self.status not in (EmbeddingJobStatus.PENDING, EmbeddingJobStatus.RUNNING):
            raise InvalidEmbeddingJobTransitionError(
                f"EmbeddingJob {self.id} nao pode falhar a partir de {self.status}."
            )
        self.status = EmbeddingJobStatus.FAILED
        self.error_message = reason
        self.finished_at = utc_now()

    def finish(
        self, *, succeeded: int, failed: int, error_message: str | None = None
    ) -> None:
        if self.status is not EmbeddingJobStatus.RUNNING:
            raise InvalidEmbeddingJobTransitionError(
                f"EmbeddingJob {self.id} nao pode finalizar a partir de {self.status}."
            )
        if failed == 0:
            self.status = EmbeddingJobStatus.COMPLETED
            self.error_message = None
        elif succeeded == 0:
            self.status = EmbeddingJobStatus.FAILED
            self.error_message = error_message
        else:
            self.status = EmbeddingJobStatus.PARTIAL
            self.error_message = error_message
        self.finished_at = utc_now()
        self.succeeded_chunks = succeeded
        self.failed_chunks = failed

    def record_metrics_from_chunks(self, chunks: list["EmbeddingJobChunk"]) -> None:
        self.total_latency_ms = sum(chunk.latency_ms or 0 for chunk in chunks)
        self.total_input_char_count = sum(chunk.input_char_count or 0 for chunk in chunks)
        self.total_estimated_input_tokens = sum(
            chunk.estimated_input_tokens or 0 for chunk in chunks
        )


@dataclass
class EmbeddingJobChunk:
    """Status de processamento de um chunk dentro de um EmbeddingJob."""

    job_id: UUID
    chunk_id: UUID
    content_hash: str | None = None

    id: UUID = field(default_factory=uuid4)
    status: EmbeddingJobChunkStatus = EmbeddingJobChunkStatus.PENDING
    attempt_count: int = 0
    model_name: str | None = None
    vector_dimension: int | None = None
    input_char_count: int | None = None
    estimated_input_tokens: int | None = None
    latency_ms: int | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None

    def complete(
        self,
        *,
        model_name: str,
        vector_dimension: int,
        input_char_count: int,
        estimated_input_tokens: int,
        latency_ms: int,
        content_hash: str,
    ) -> None:
        self.status = EmbeddingJobChunkStatus.COMPLETED
        self.model_name = model_name
        self.vector_dimension = vector_dimension
        self.input_char_count = input_char_count
        self.estimated_input_tokens = estimated_input_tokens
        self.latency_ms = latency_ms
        self.content_hash = content_hash
        self.error_message = None
        self.finished_at = utc_now()

    def record_failure(self, reason: str) -> None:
        self.attempt_count += 1
        self.error_message = reason
        if self.attempt_count >= MAX_CHUNK_ATTEMPTS:
            self.status = EmbeddingJobChunkStatus.FAILED
            self.finished_at = utc_now()


def estimate_input_tokens(text: str) -> int:
    """Estimativa simples e deterministica para metricas operacionais."""

    return max(1, (len(text) + 3) // 4)


def chunk_content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()
