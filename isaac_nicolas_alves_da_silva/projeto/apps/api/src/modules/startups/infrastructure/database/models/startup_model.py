"""Model SQLAlchemy da tabela startups."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class StartupModel(Base):
    __tablename__ = "startups"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_maturity_level: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    classification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    founders: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    funding_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    funding_amount_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    customers: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    ai_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    field_confidence: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    field_evidence_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
