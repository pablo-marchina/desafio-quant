"""Model SQLAlchemy da tabela embedding_jobs."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class EmbeddingJobModel(Base):
    __tablename__ = "embedding_jobs"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_input_char_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_estimated_input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
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
