"""DTOs do modulo RAG."""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class SearchEvidenceInput:
    query: str
    limit: int = 5
    source_type: str | None = None
    document_ids: list[UUID] | None = None


@dataclass
class EvidenceChunkView:
    chunk_id: UUID
    document_id: UUID
    source_url: str
    text: str
    score: float
    source_type: str = "startup_evidence"


@dataclass
class SearchEvidenceView:
    query: str
    results: list[EvidenceChunkView]


@dataclass
class LexicalSearchResult:
    """Resultado da busca lexical (Postgres full-text search)."""

    chunk_id: UUID
    document_id: UUID
    score: float


@dataclass
class GenerateRagAnswerInput:
    query: str
    evidences: list[EvidenceChunkView]


@dataclass
class RagCitationView:
    chunk_id: UUID
    document_id: UUID
    source_url: str
    quote: str


@dataclass
class RagAnswerView:
    query: str
    answer: str
    citations: list[RagCitationView]
    evidences: list[EvidenceChunkView]


@dataclass
class AnswerQuestionInput:
    query: str
    limit: int = 5
    source_type: str | None = None
    document_ids: list[UUID] | None = None
