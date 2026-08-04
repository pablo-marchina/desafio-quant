"""Model SQLAlchemy da tabela startup_discovery_runs."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class DiscoveryRunModel(Base):
    __tablename__ = "startup_discovery_runs"

    id: Mapped[PostgresUUID] = mapped_column(
        PostgresUUID(as_uuid=True), primary_key=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    hubs_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    urls_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_submitted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_enriched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
