"""Modelos SQLModel — persistência relacional do TAPI (F0.6).

Seis tabelas (espelham os contratos de `packages.schemas`):
- `run`            — um run do grafo (ARQUITETURA §3); chave do `GraphState`.
- `company`        — startup (dimensões do §2); founders normalizados, demais
                     sub-estruturas (produtos/clientes/tecnologias/funding) em JSON.
- `founder`        — liderança (só info profissional pública — §2/LGPD).
- `evidence`       — tabela de proveniência **polimórfica** (URL+hash+fetched_at);
                     liga-se a qualquer entidade via (`entity_type`, `entity_id`,
                     `field`). Sustenta o princípio "tudo com evidência" (§8).
- `score`          — AIMI persistido (4 pilares 0–25 + total + classe + prioridade).
- `recommendation` — recomendação §5.5 (evidência dos dois lados via `evidence`).

Enums vêm de `packages.schemas.enums` e são gravados como VARCHAR+CHECK
(`native_enum=False`) — portável (Postgres em prod, SQLite em teste) e simples p/ Alembic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from packages.schemas.enums import (
    AIMIPillar,
    BriefingStatus,
    Classification,
    Complexity,
    ExecutionMode,
    HITLMode,
    Priority,
    RunStatus,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _enum(enum_cls: type, *, nullable: bool = False) -> Column:
    """Coluna de enum portável (VARCHAR + CHECK, sem tipo nativo do Postgres)."""
    return Column(SAEnum(enum_cls, native_enum=False, length=40), nullable=nullable)


class Run(SQLModel, table=True):
    """Um run do grafo (1 consulta → 1 perfil). Raiz de rastreabilidade."""

    __tablename__ = "run"

    id: str = Field(primary_key=True, description="run_id (ex.: uuid).")
    query: str
    mode: ExecutionMode = Field(
        default=ExecutionMode.SINGLE_COMPANY, sa_column=_enum(ExecutionMode)
    )
    hitl: HITLMode = Field(default=HITLMode.SYNC, sa_column=_enum(HITLMode))
    status: RunStatus = Field(default=RunStatus.PENDING, sa_column=_enum(RunStatus))
    briefing_status: BriefingStatus | None = Field(
        default=None, sa_column=_enum(BriefingStatus, nullable=True)
    )
    prompt_version: str | None = None
    retry_count: int = 0
    error: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(
        default_factory=_now, sa_column_kwargs={"onupdate": _now}
    )


class Company(SQLModel, table=True):
    """Startup coletada (§2). Upsert/dedup por CNPJ > domínio > (nome, país) (F1.10)."""

    __tablename__ = "company"
    __table_args__ = (UniqueConstraint("nome", "pais", name="uq_company_nome_pais"),)

    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(index=True)
    website: str | None = None
    # Chaves de dedup do cohort builder (F1.10/F1.14). Únicas **quando presentes** (NULLs
    # distintos em SQLite e Postgres → várias empresas sem chave não colidem).
    domain: str | None = Field(
        default=None,
        index=True,
        unique=True,
        description="Host normalizado do website (sem www) — chave de dedup forte (F1.10).",
    )
    cnpj: str | None = Field(
        default=None,
        index=True,
        unique=True,
        description="CNPJ só-dígitos (14, válido) — dedup forte + sinal de operação BR (F1.10).",
    )
    pais: str = Field(default="BR", index=True)
    descricao: str | None = Field(default=None, sa_column=Column(Text))
    setor: str | None = Field(default=None, index=True)
    ano_fundacao: int | None = None

    # Sub-estruturas ricas (proveniência por item dentro do JSON). Founders são
    # normalizados em tabela própria; estes ficam em JSON (escopo das 6 tabelas).
    produtos: list = Field(default_factory=list, sa_column=Column(JSON))
    clientes: list = Field(default_factory=list, sa_column=Column(JSON))
    tecnologias: list = Field(default_factory=list, sa_column=Column(JSON))
    funding: dict | None = Field(default=None, sa_column=Column(JSON))

    run_id: str | None = Field(default=None, foreign_key="run.id", index=True)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(
        default_factory=_now, sa_column_kwargs={"onupdate": _now}
    )


class Founder(SQLModel, table=True):
    """Fundador/liderança — apenas info profissional pública (§2/LGPD)."""

    __tablename__ = "founder"

    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    nome: str
    cargo: str | None = None
    linkedin_url: str | None = None
    background: str | None = Field(default=None, sa_column=Column(Text))


class Evidence(SQLModel, table=True):
    """Proveniência polimórfica: liga uma fonte citável a qualquer entidade/campo.

    `entity_type` ∈ {company, founder, score, recommendation}; `field` refina o alvo
    (ex.: 'descricao', 'data_moat', 'gap', 'nvidia'). Sustenta a auditoria do §8.
    """

    __tablename__ = "evidence"

    id: int | None = Field(default=None, primary_key=True)
    url: str
    snippet: str = Field(sa_column=Column(Text))
    fetched_at: datetime
    content_hash: str | None = Field(default=None, index=True)
    source_title: str | None = None

    entity_type: str = Field(index=True)
    entity_id: int = Field(index=True)
    field: str | None = Field(
        default=None, description="Campo/pilar/lado que a evidência sustenta."
    )
    legal_basis: str | None = Field(
        default=None,
        description="Base legal LGPD da coleta (F1.13, `LegalBasis`); preenchida p/ founder.",
    )
    source_policy: str | None = Field(
        default=None,
        description="Política de ToS da fonte (F1.15): '<fonte>:<policy>' (allowlist/denylist).",
    )
    created_at: datetime = Field(default_factory=_now)


class Score(SQLModel, table=True):
    """AIMI persistido: 4 pilares (0–25) + total (0–100) + classe + prioridade."""

    __tablename__ = "score"

    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    run_id: str | None = Field(default=None, foreign_key="run.id", index=True)

    classificacao: Classification = Field(sa_column=_enum(Classification))
    confidence: float | None = None
    total: int = Field(ge=0, le=100)
    inception_priority: int | None = Field(default=None, ge=0, le=100)
    heuristic_version: str = "v0"

    data_moat: int = Field(ge=0, le=25)
    workflow_depth: int = Field(ge=0, le=25)
    technical_optimization: int = Field(ge=0, le=25)
    distribution_moat: int = Field(ge=0, le=25)

    just_data_moat: str | None = Field(default=None, sa_column=Column(Text))
    just_workflow_depth: str | None = Field(default=None, sa_column=Column(Text))
    just_technical_optimization: str | None = Field(default=None, sa_column=Column(Text))
    just_distribution_moat: str | None = Field(default=None, sa_column=Column(Text))

    created_at: datetime = Field(default_factory=_now)


class Recommendation(SQLModel, table=True):
    """Recomendação §5.5. Evidência dos dois lados via tabela `evidence`
    (`field='gap'` lado startup / `field='nvidia'` lado KB)."""

    __tablename__ = "recommendation"

    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    run_id: str | None = Field(default=None, foreign_key="run.id", index=True)

    tech: str = Field(index=True)
    justificativa_tecnica: str = Field(sa_column=Column(Text))
    justificativa_negocio: str = Field(sa_column=Column(Text))
    prioridade: Priority = Field(sa_column=_enum(Priority))
    complexidade: Complexity = Field(sa_column=_enum(Complexity))
    proxima_acao: str = Field(sa_column=Column(Text))
    pilar_origem: AIMIPillar | None = Field(
        default=None, sa_column=_enum(AIMIPillar, nullable=True)
    )
    roi: dict | None = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=_now)


__all__ = ["Run", "Company", "Founder", "Evidence", "Score", "Recommendation"]
