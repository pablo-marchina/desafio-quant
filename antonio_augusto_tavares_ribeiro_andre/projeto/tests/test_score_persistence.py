"""Testes da persistência do AIMI (F6.13 — fecha a lacuna anotada na F6.13).

Offline, numa sessão SQLite isolada (mesmo padrão de `test_recommendation_persistence.py`).
Provam o contrato: o `AIMIScore` (saída do classifier, F2.6/F6.1) grava na tabela `score` e a
evidência de **cada pilar** liga na tabela `evidence` polimórfica (`entity_type='score'`,
`field=<pilar>`), com upsert idempotente por `(run_id, company_id)`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from packages.agents.persistence import persist_score
from packages.db.models import Company, Evidence, Run
from packages.db.models import Score as ScoreRow
from packages.schemas.aimi import AIMIScore, PillarScore
from packages.schemas.enums import AIMIPillar, Classification, RunStatus
from packages.schemas.evidence import Evidence as EvidenceSchema


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


def _ev(url: str, snippet: str) -> EvidenceSchema:
    return EvidenceSchema(
        url=url,
        snippet=snippet,
        fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
        content_hash=f"hash-{snippet[:8]}",
    )


def _company(session: Session) -> Company:
    run = Run(id="run-1", query="Acme AI", status=RunStatus.COMPLETED)
    company = Company(nome="Acme AI", pais="BR", run_id="run-1")
    session.add(run)
    session.add(company)
    session.flush()
    return company


def _pillar(pilar: AIMIPillar, score: int, *, ev: bool = True) -> PillarScore:
    # RUBRICA §0: sub-score > 6 exige evidência; abaixo disso pode vir sem.
    evidencia = [_ev(f"https://acme.com.br/{pilar.value}", f"sinal de {pilar.value}")] if ev else []
    return PillarScore(
        pilar=pilar, score=score, justificativa=f"cálculo de {pilar.value}", evidencia=evidencia
    )


def _aimi(
    *,
    classificacao: Classification = Classification.AI_NATIVE,
    inception: int | None = 72,
    version: str = "v1",
) -> AIMIScore:
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, 18),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, 20),
        technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, 5, ev=False),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, 12),
        classificacao=classificacao,
        confidence=0.9,
        inception_priority=inception,
        heuristic_version=version,
    )


def test_persists_score_row(session: Session) -> None:
    company = _company(session)
    row = persist_score(session, _aimi(), company_id=company.id, run_id="run-1")
    session.commit()

    assert row.id is not None
    saved = session.exec(select(ScoreRow)).one()
    assert saved.company_id == company.id
    assert saved.run_id == "run-1"
    assert saved.classificacao is Classification.AI_NATIVE
    assert saved.confidence == 0.9
    assert saved.inception_priority == 72
    assert saved.heuristic_version == "v1"


def test_persists_four_pillars_and_total(session: Session) -> None:
    company = _company(session)
    persist_score(session, _aimi(), company_id=company.id, run_id="run-1")
    session.commit()

    saved = session.exec(select(ScoreRow)).one()
    assert saved.data_moat == 18
    assert saved.workflow_depth == 20
    assert saved.technical_optimization == 5
    assert saved.distribution_moat == 12
    # Total é a soma derivada pelo schema (fonte única), materializada na linha.
    assert saved.total == 18 + 20 + 5 + 12
    assert saved.just_data_moat == "cálculo de data_moat"


def test_links_evidence_per_pillar(session: Session) -> None:
    company = _company(session)
    row = persist_score(session, _aimi(), company_id=company.id, run_id="run-1")
    session.commit()

    score_ev = session.exec(
        select(Evidence).where(
            Evidence.entity_type == "score", Evidence.entity_id == row.id
        )
    ).all()
    # 3 pilares com evidência (technical_optimization veio sem, score ≤ 6).
    assert {e.field for e in score_ev} == {"data_moat", "workflow_depth", "distribution_moat"}
    data_moat = next(e for e in score_ev if e.field == "data_moat")
    assert "data_moat" in data_moat.snippet


def test_is_idempotent_within_run(session: Session) -> None:
    company = _company(session)
    # Reprocessa o mesmo run (ex.: retry do worker) → enriquece, não duplica.
    persist_score(session, _aimi(), company_id=company.id, run_id="run-1")
    persist_score(session, _aimi(), company_id=company.id, run_id="run-1")
    session.commit()

    assert len(session.exec(select(ScoreRow)).all()) == 1
    score_ev = session.exec(select(Evidence).where(Evidence.entity_type == "score")).all()
    assert len(score_ev) == 3  # 3 pilares com evidência, sem duplicar


def test_upsert_enriches_on_hit(session: Session) -> None:
    company = _company(session)
    persist_score(session, _aimi(inception=50), company_id=company.id, run_id="run-1")
    # Mesmo run/empresa, prioridade e classe revistas → atualiza a linha existente.
    persist_score(
        session,
        _aimi(classificacao=Classification.AI_ENABLED, inception=88),
        company_id=company.id,
        run_id="run-1",
    )
    session.commit()

    saved = session.exec(select(ScoreRow)).one()
    assert saved.classificacao is Classification.AI_ENABLED
    assert saved.inception_priority == 88


def test_distinct_runs_keep_separate_rows(session: Session) -> None:
    company = _company(session)
    session.add(Run(id="run-2", query="Acme AI", status=RunStatus.COMPLETED))
    session.flush()
    persist_score(session, _aimi(), company_id=company.id, run_id="run-1")
    persist_score(session, _aimi(), company_id=company.id, run_id="run-2")
    session.commit()

    assert len(session.exec(select(ScoreRow)).all()) == 2
