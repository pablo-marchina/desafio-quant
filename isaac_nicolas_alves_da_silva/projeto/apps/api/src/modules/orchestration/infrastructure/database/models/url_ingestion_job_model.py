"""Model SQLAlchemy da tabela url_ingestion_jobs."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class UrlIngestionJobModel(Base):
    __tablename__ = "url_ingestion_jobs"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="startup_evidence",
        server_default="startup_evidence",
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scraping_job_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    scraping_result_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    ingestion_job_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    embedding_job_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    startup_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    parent_job_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True, index=True
    )
    enrichment_round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    evidence_attached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    recommendations_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    recommendation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    briefing_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
