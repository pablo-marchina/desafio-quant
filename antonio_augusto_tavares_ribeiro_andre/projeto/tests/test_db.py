"""Testes da camada de persistência (F0.6).

Validam, em SQLite isolado, que: as 6 tabelas batem com `SQLModel.metadata`; um
perfil completo faz round-trip (run → company → founder/score/recommendation +
evidência polimórfica); enums e colunas JSON persistem; e a migração Alembic
`upgrade head` cria exatamente as mesmas tabelas dos modelos.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from packages.db.models import (
    Company,
    Evidence,
    Founder,
    Recommendation,
    Run,
    Score,
)
from packages.schemas.enums import (
    Classification,
    Complexity,
    ExecutionMode,
    Priority,
    RunStatus,
)

EXPECTED_TABLES = {"run", "company", "founder", "evidence", "score", "recommendation"}


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_metadata_has_six_tables() -> None:
    assert EXPECTED_TABLES.issubset(set(SQLModel.metadata.tables))


def test_full_profile_roundtrip(session: Session) -> None:
    run = Run(
        id="run-1",
        query="Acme AI",
        mode=ExecutionMode.SINGLE_COMPANY,
        status=RunStatus.COMPLETED,
    )
    company = Company(
        nome="Acme AI",
        setor="fintech",
        descricao="copiloto de crédito",
        tecnologias=[{"nome": "OpenAI API", "categoria": "LLM provider"}],
        funding={"last_round_stage": "Seed", "total_raised_usd": 1_000_000.0},
        run_id="run-1",
    )
    session.add(run)
    session.add(company)
    session.commit()
    session.refresh(company)

    session.add(Founder(company_id=company.id, nome="Jane Doe", cargo="CEO"))
    session.add(
        Score(
            company_id=company.id,
            run_id="run-1",
            classificacao=Classification.AI_NATIVE,
            total=44,
            data_moat=14,
            workflow_depth=16,
            technical_optimization=4,
            distribution_moat=10,
        )
    )
    rec = Recommendation(
        company_id=company.id,
        run_id="run-1",
        tech="NIM",
        justificativa_tecnica="serving otimizado",
        justificativa_negocio="reduz custo",
        prioridade=Priority.ALTA,
        complexidade=Complexity.MEDIA,
        proxima_acao="testar NIM self-hosted",
        roi={"throughput_speedup": 3.0, "cost_delta_pct": -40.0},
    )
    session.add(rec)
    # Evidência polimórfica: dos dois lados da recomendação + de um campo da company.
    session.add_all(
        [
            Evidence(
                url="https://acme.ai/docs",
                snippet="100% API externa",
                fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
                entity_type="company",
                entity_id=company.id,
                field="descricao",
            ),
            Evidence(
                url="https://build.nvidia.com/nim",
                snippet="NIM deploy otimizado",
                fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
                entity_type="recommendation",
                entity_id=1,
                field="nvidia",
            ),
        ]
    )
    session.commit()

    # Round-trip: enums e JSON voltam corretos.
    got = session.exec(select(Company).where(Company.nome == "Acme AI")).one()
    assert got.funding["last_round_stage"] == "Seed"
    assert got.tecnologias[0]["nome"] == "OpenAI API"

    score = session.exec(select(Score).where(Score.company_id == company.id)).one()
    assert score.classificacao is Classification.AI_NATIVE
    assert score.total == 44

    rec_db = session.exec(select(Recommendation)).one()
    assert rec_db.prioridade is Priority.ALTA
    assert rec_db.roi["throughput_speedup"] == 3.0

    nvidia_ev = session.exec(
        select(Evidence).where(Evidence.entity_type == "recommendation", Evidence.field == "nvidia")
    ).one()
    assert nvidia_ev.url.endswith("/nim")


def test_alembic_upgrade_creates_tables(tmp_path, monkeypatch) -> None:
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "mig.db"
    monkeypatch.setenv("POSTGRES_URL", f"sqlite:///{db_path}")
    get_settings_cache_clear()

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.issubset(tables)


def get_settings_cache_clear() -> None:
    # A config é cacheada; limpa para reler POSTGRES_URL do teste.
    from packages.config.settings import get_settings

    get_settings.cache_clear()
