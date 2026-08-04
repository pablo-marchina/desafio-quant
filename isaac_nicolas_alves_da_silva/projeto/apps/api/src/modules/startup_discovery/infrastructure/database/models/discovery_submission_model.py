"""Model SQLAlchemy da tabela startup_discovery_submissions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class DiscoverySubmissionModel(Base):
    __tablename__ = "startup_discovery_submissions"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("startup_discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hub_name: Mapped[str] = mapped_column(String(128), nullable=False)
    website_url: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hub_profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    declared_sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
