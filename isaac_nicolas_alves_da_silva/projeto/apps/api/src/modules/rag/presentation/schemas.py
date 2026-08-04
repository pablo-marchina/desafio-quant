"""Schemas Pydantic do modulo RAG."""

from uuid import UUID

from pydantic import BaseModel, Field

from apps.api.src.modules.rag.application.dto import (
    EvidenceChunkView,
    RagAnswerView,
    RagCitationView,
    SearchEvidenceView,
)


class SearchEvidenceRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=20)
    source_type: str | None = None
    document_ids: list[UUID] | None = None


class AnswerQuestionRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=20)
    source_type: str | None = None
    document_ids: list[UUID] | None = None


class EvidenceChunkResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    source_url: str
    source_type: str
    text: str
    score: float

    @classmethod
    def from_view(cls, view: EvidenceChunkView) -> "EvidenceChunkResponse":
        return cls(
            chunk_id=view.chunk_id,
            document_id=view.document_id,
            source_url=view.source_url,
            source_type=view.source_type,
            text=view.text,
            score=view.score,
        )


class SearchEvidenceResponse(BaseModel):
    query: str
    results: list[EvidenceChunkResponse]

    @classmethod
    def from_view(cls, view: SearchEvidenceView) -> "SearchEvidenceResponse":
        return cls(
            query=view.query,
            results=[
                EvidenceChunkResponse.from_view(result) for result in view.results
            ],
        )


class RagCitationResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    source_url: str
    quote: str

    @classmethod
    def from_view(cls, view: RagCitationView) -> "RagCitationResponse":
        return cls(
            chunk_id=view.chunk_id,
            document_id=view.document_id,
            source_url=view.source_url,
            quote=view.quote,
        )


class RagAnswerResponse(BaseModel):
    query: str
    answer: str
    citations: list[RagCitationResponse]
    evidences: list[EvidenceChunkResponse]

    @classmethod
    def from_view(cls, view: RagAnswerView) -> "RagAnswerResponse":
        return cls(
            query=view.query,
            answer=view.answer,
            citations=[
                RagCitationResponse.from_view(citation)
                for citation in view.citations
            ],
            evidences=[
                EvidenceChunkResponse.from_view(evidence)
                for evidence in view.evidences
            ],
        )
