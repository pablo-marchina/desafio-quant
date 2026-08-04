from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AiMaturityLabel,
    ClaimValidationStatus,
    ImplementationComplexity,
    RecommendationPriority,
    SourceType,
    WorkflowRunStatus,
    WorkflowRunType,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WorkflowRun(Base, TimestampMixin):
    __tablename__ = "workflow_runs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WorkflowRunType.DISCOVERY
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WorkflowRunStatus.PENDING
    )
    query: Mapped[str | None] = mapped_column(Text)
    startup_url: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)


class Startup(Base, TimestampMixin):
    __tablename__ = "startups"

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("country", "Brazil")
        super().__init__(**kwargs)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(String(120), nullable=False, default="Brazil")
    city: Mapped[str | None] = mapped_column(String(120))
    sector: Mapped[str | None] = mapped_column(String(180), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    funding_stage: Mapped[str | None] = mapped_column(String(120))
    product_summary: Mapped[str | None] = mapped_column(Text)
    ai_usage_summary: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float)

    founders: Mapped[list["Founder"]] = relationship(
        secondary="startup_founders", back_populates="startups"
    )
    source_documents: Mapped[list["SourceDocument"]] = relationship(back_populates="startup")


class Founder(Base, TimestampMixin):
    __tablename__ = "founders"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(String(160))

    startups: Mapped[list[Startup]] = relationship(
        secondary="startup_founders", back_populates="founders"
    )


class StartupFounder(Base):
    __tablename__ = "startup_founders"

    startup_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("startups.id"), primary_key=True
    )
    founder_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("founders.id"), primary_key=True
    )


class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    startup_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("startups.id"))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default=SourceType.OTHER)
    title: Mapped[str | None] = mapped_column(Text)
    raw_content_location: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    scrape_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    scrape_error: Mapped[str | None] = mapped_column(Text)

    startup: Mapped[Startup | None] = relationship(back_populates="source_documents")
    evidence_claims: Mapped[list["EvidenceClaim"]] = relationship(back_populates="source_document")


class EvidenceClaim(Base, TimestampMixin):
    __tablename__ = "evidence_claims"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    startup_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("startups.id"))
    source_document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_documents.id")
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(120), nullable=False)
    supporting_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    extracted_by: Mapped[str | None] = mapped_column(String(120))
    validation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ClaimValidationStatus.PENDING
    )

    source_document: Mapped[SourceDocument] = relationship(back_populates="evidence_claims")


class AiMaturityAssessment(Base, TimestampMixin):
    __tablename__ = "ai_maturity_assessments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    startup_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("startups.id"))
    label: Mapped[str] = mapped_column(String(32), nullable=False, default=AiMaturityLabel.NON_AI)
    confidence: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text)
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class TechnologySignal(Base, TimestampMixin):
    __tablename__ = "technology_signals"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    startup_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("startups.id"))
    technology_name: Mapped[str] = mapped_column(String(180), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_claim_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_claims.id")
    )


class NvidiaTechnology(Base, TimestampMixin):
    __tablename__ = "nvidia_technologies"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)


class NvidiaKnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "nvidia_knowledge_documents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    technology_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nvidia_technologies.id")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=SourceType.NVIDIA_DOC
    )
    product_area: Mapped[str | None] = mapped_column(String(120))
    content_hash: Mapped[str | None] = mapped_column(String(128))


class NvidiaKnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "nvidia_knowledge_chunks"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nvidia_knowledge_documents.id")
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(String(255))
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    startup_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("startups.id"))
    gap_addressed: Mapped[str] = mapped_column(String(180), nullable=False)
    nvidia_technology_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nvidia_technologies.id")
    )
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RecommendationPriority.MEDIUM
    )
    complexity: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ImplementationComplexity.MEDIUM
    )
    technical_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    business_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    next_action: Mapped[str] = mapped_column(Text, nullable=False)


class RecommendationEvidence(Base):
    __tablename__ = "recommendation_evidence"

    recommendation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendations.id"), primary_key=True
    )
    evidence_claim_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_claims.id"), primary_key=True
    )


class Briefing(Base, TimestampMixin):
    __tablename__ = "briefings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    startup_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("startups.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    source_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
