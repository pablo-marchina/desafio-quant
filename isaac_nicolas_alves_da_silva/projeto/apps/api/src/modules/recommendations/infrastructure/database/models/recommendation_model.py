"""Model SQLAlchemy da tabela recommendations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    startup_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("startups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    technology_slug: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    technology_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    complexity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    matched_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    signal_origins: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    missing_signals: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    nivel: Mapped[str] = mapped_column(
        String(32), nullable=False, default="exploratoria"
    )
    faltando: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
