"""Model SQLAlchemy da tabela de tentativas de scraping."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class ScrapingAttemptModel(Base):
    """Representação relacional de cada estratégia tentada por um job."""

    __tablename__ = "scraping_attempts"
    __table_args__ = (
        CheckConstraint(
            "technical_score BETWEEN 0 AND 1",
            name="technical_score_range",
        ),
        CheckConstraint(
            "text_score BETWEEN 0 AND 1",
            name="text_score_range",
        ),
        CheckConstraint(
            "evidence_score BETWEEN 0 AND 1",
            name="evidence_score_range",
        ),
        CheckConstraint(
            "quality_score BETWEEN 0 AND 1",
            name="quality_score_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )

    # A chave estrangeira garante que nenhuma tentativa exista sem um job.
    # CASCADE remove tentativas automaticamente caso o job seja removido.
    job_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("scraping_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    method: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Scores permanecem opcionais enquanto a tentativa ainda está running ou
    # quando ocorre falha técnica antes da validação.
    technical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # JSONB preserva as listas e permite consultas futuras por problema.
    problems: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    warnings: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    semantic_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    agent_reviewed: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    agent_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
