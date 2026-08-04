"""Model SQLAlchemy da tabela de resultados de scraping.

Este model representa a entidade ``ScrapingResult`` do domínio: o conteúdo
bruto que passou pela validação e foi aceito para seguir no pipeline.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.src.database.relational.base import Base


class ScrapingResultModel(Base):
    """Representação relacional de ``ScrapingResult``.

    Cada linha desta tabela é o conteúdo aprovado de UM job. Um job só pode
    ter, no máximo, um resultado — por isso ``job_id`` é único.
    """

    __tablename__ = "scraping_results"
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
        CheckConstraint(
            "status_code BETWEEN 100 AND 599",
            name="status_code_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )

    # Liga o resultado ao job que o originou. unique=True garante a relação
    # 1-para-1 entre scraping_jobs e scraping_results no nível do banco.
    # ondelete="CASCADE": se o job for removido, o resultado some com ele.
    job_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("scraping_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # URL original solicitada e URL final após redirecionamentos (podem
    # divergir quando o site faz redirect, ex: http -> https ou www).
    url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Título da página. Nem toda página tem <title>, por isso é opcional.
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Conteúdo bruto coletado. Guardamos o HTML inteiro para permitir
    # reprocessamento futuro (ex: se a extração de texto melhorar).
    raw_html: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Qual tecnologia (beautifulsoup, playwright, ...) produziu este
    # resultado. Usamos String, assim como em scraping_attempts.
    method: Mapped[str] = mapped_column(String(32), nullable=False)

    # Código HTTP retornado pela requisição que gerou este resultado.
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)

    # Os quatro scores que justificaram a decisão ACCEPT da validação
    # determinística. São os mesmos campos presentes em scraping_attempts,
    # mas aqui representam o "snapshot" da tentativa que foi aprovada.
    technical_score: Mapped[float] = mapped_column(Float, nullable=False)
    text_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Hash (ex: SHA-256) do conteúdo, usado para detectar duplicados sem
    # comparar o texto inteiro. Indexado porque a busca por duplicidade é
    # uma operação esperada (ver docs: "índice por content_hash").
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        unique=True,
    )

    # Campo flexível para informações extras que não merecem coluna própria
    # (ex: headers relevantes, contagem de palavras). JSONB permite indexar
    # e consultar chaves específicas no PostgreSQL, se necessário no futuro.
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
