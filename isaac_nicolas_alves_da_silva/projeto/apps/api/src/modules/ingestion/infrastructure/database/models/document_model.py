"""Model SQLAlchemy da tabela documents."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    ingestion_job_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    scraping_result_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(length=64),
        nullable=False,
        default="startup_evidence",
        server_default="startup_evidence",
        index=True,
    )
    # SHA-256 hex do clean_text — nullable para documentos criados antes desta migracao.
    # Novos documentos sempre recebem o hash; a busca por hash so casa com valores nao-nulos.
    content_hash: Mapped[str | None] = mapped_column(
        String(length=64),
        nullable=True,
        index=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
