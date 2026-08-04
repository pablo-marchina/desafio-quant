"""Model SQLAlchemy da tabela de jobs de scraping."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class ScrapingJobModel(Base):
    """Representação relacional de ``ScrapingJob``.

    Este model descreve como os dados são armazenados no PostgreSQL. Ele não
    substitui a entidade do domínio, que continua responsável pelas regras de
    transição de estado.
    """

    __tablename__ = "scraping_jobs"

    # UUID nativo do PostgreSQL evita armazenar identificadores como texto.
    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )

    # A URL pode ser longa, então utilizamos Text em vez de String limitado.
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # O banco armazena o valor textual do enum, como pending ou completed.
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="startup_evidence",
    )

    # timezone=True preserva timestamps com fuso horário no PostgreSQL.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
