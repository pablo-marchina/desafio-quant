"""Model SQLAlchemy da tabela startup_discovery_candidates."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class DiscoveryCandidateModel(Base):
    __tablename__ = "startup_discovery_candidates"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), nullable=False)
    discovery_source: Mapped[str] = mapped_column(String(128), nullable=False)
    discovery_source_url: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    official_site_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    enrichment_sources: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="discovered", index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_ingestion_job_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
