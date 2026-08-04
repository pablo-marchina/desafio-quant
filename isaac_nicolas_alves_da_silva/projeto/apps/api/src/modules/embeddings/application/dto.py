"""DTOs do modulo embeddings."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.api.src.modules.embeddings.domain.enums import EmbeddingJobStatus


@dataclass
class GenerateChunkEmbeddingInput:
    chunk_id: UUID
    text: str


@dataclass
class ChunkEmbeddingView:
    chunk_id: UUID
    values: tuple[float, ...]
    dimension: int
    model_name: str


@dataclass
class UpsertChunkEmbeddingInput:
    chunk_id: UUID
    document_id: UUID
    source_url: str
    text: str
    source_type: str = "startup_evidence"


@dataclass
class ChunkEmbeddingRecord:
    chunk_id: UUID
    document_id: UUID
    source_url: str
    values: tuple[float, ...]
    dimension: int
    model_name: str
    source_type: str = "startup_evidence"


@dataclass
class ChunkSearchResult:
    chunk_id: UUID
    document_id: UUID
    source_url: str
    score: float
    source_type: str = "startup_evidence"


@dataclass
class ChunkSourceItem:
    chunk_id: UUID
    text: str
    source_url: str
    source_type: str = "startup_evidence"


@dataclass
class CreateEmbeddingJobInput:
    document_id: UUID


@dataclass
class EmbeddingJobView:
    id: UUID
    document_id: UUID
    status: EmbeddingJobStatus
    total_chunks: int
    succeeded_chunks: int
    failed_chunks: int
    total_latency_ms: int
    total_input_char_count: int
    total_estimated_input_tokens: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
