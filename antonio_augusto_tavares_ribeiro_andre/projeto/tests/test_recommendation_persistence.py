"""Testes da persistência das recomendações (F4.7).

Offline, numa sessão SQLite isolada (mesmo padrão de `test_persistence.py`/`test_db.py`).
Provam o contrato F4.7: a recomendação §5.5 grava na tabela `recommendation` e a evidência
dos **dois lados** liga na tabela `evidence` polimórfica (`field='gap'` lado startup /
`field='nvidia'` lado KB), com upsert idempotente por `(run_id, company_id, tech)`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from packages.agents.persistence import persist_recommendations
from packages.db.models import Company, Evidence, Run
from packages.db.models import Recommendation as RecommendationRow
from packages.schemas.enums import AIMIPillar, Complexity, Priority, RunStatus
from packages.schemas.evidence import Evidence as EvidenceSchema
from packages.schemas.recommendation import Recommendation, ROIEstimate


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


def _rec(tech: str = "NIM", *, roi: ROIEstimate | None = None) -> Recommendation:
    return Recommendation(
        tech=tech,
        justificativa_tecnica="serving otimizado com batching",
        justificativa_negocio="reduz custo de inferência",
        prioridade=Priority.ALTA,
        complexidade=Complexity.MEDIA,
        proxima_acao="testar NIM self-hosted no catálogo",
        pilar_origem=AIMIPillar.TECHNICAL_OPTIMIZATION,
        evidencia_gap=[_ev("https://acme.com.br/produto", "100% via API externa")],
        evidencia_nvidia=[_ev("https://build.nvidia.com/nim", "NIM: deploy otimizado")],
        roi=roi,
    )


def test_persists_recommendation_row(session: Session) -> None:
    company = _company(session)
    rows = persist_recommendations(session, [_rec()], company_id=company.id, run_id="run-1")
    session.commit()

    assert len(rows) == 1 and rows[0].id is not None
    saved = session.exec(select(RecommendationRow)).one()
    assert saved.tech == "NIM"
    assert saved.company_id == company.id
    assert saved.run_id == "run-1"
    assert saved.prioridade is Priority.ALTA
    assert saved.complexidade is Complexity.MEDIA
    assert saved.pilar_origem is AIMIPillar.TECHNICAL_OPTIMIZATION


def test_links_evidence_from_both_sides(session: Session) -> None:
    company = _company(session)
    [row] = persist_recommendations(session, [_rec()], company_id=company.id, run_id="run-1")
    session.commit()

    rec_ev = session.exec(
        select(Evidence).where(
            Evidence.entity_type == "recommendation", Evidence.entity_id == row.id
        )
    ).all()
    # Um de cada lado, ligados ao id da recomendação.
    assert {e.field for e in rec_ev} == {"gap", "nvidia"}
    nvidia = next(e for e in rec_ev if e.field == "nvidia")
    assert nvidia.url.endswith("/nim")
    gap = next(e for e in rec_ev if e.field == "gap")
    assert "API externa" in gap.snippet


def test_serializes_roi_to_json(session: Session) -> None:
    company = _company(session)
    roi = ROIEstimate(throughput_speedup=3.0, cost_delta_pct=-40.0, baseline="API externa")
    persist_recommendations(session, [_rec(roi=roi)], company_id=company.id, run_id="run-1")
    session.commit()

    saved = session.exec(select(RecommendationRow)).one()
    assert saved.roi["throughput_speedup"] == 3.0
    assert saved.roi["cost_delta_pct"] == -40.0


def test_roi_is_none_when_absent(session: Session) -> None:
    company = _company(session)
    persist_recommendations(session, [_rec()], company_id=company.id, run_id="run-1")
    session.commit()
    assert session.exec(select(RecommendationRow)).one().roi is None


def test_is_idempotent_within_run(session: Session) -> None:
    company = _company(session)
    # Reprocessa o mesmo run (ex.: retry do worker) → enriquece, não duplica.
    persist_recommendations(session, [_rec()], company_id=company.id, run_id="run-1")
    persist_recommendations(session, [_rec()], company_id=company.id, run_id="run-1")
    session.commit()

    assert len(session.exec(select(RecommendationRow)).all()) == 1
    rec_ev = session.exec(select(Evidence).where(Evidence.entity_type == "recommendation")).all()
    assert len(rec_ev) == 2  # gap + nvidia, sem duplicar


def test_upsert_enriches_on_hit(session: Session) -> None:
    company = _company(session)
    persist_recommendations(session, [_rec()], company_id=company.id, run_id="run-1")
    # Mesma tech/run, agora com prioridade revista → atualiza a linha existente.
    updated = _rec()
    updated = updated.model_copy(update={"prioridade": Priority.MEDIA})
    persist_recommendations(session, [updated], company_id=company.id, run_id="run-1")
    session.commit()

    saved = session.exec(select(RecommendationRow)).one()
    assert saved.prioridade is Priority.MEDIA


def test_persists_multiple_techs(session: Session) -> None:
    company = _company(session)
    rows = persist_recommendations(
        session, [_rec("NIM"), _rec("TensorRT-LLM")], company_id=company.id, run_id="run-1"
    )
    session.commit()

    assert {r.tech for r in rows} == {"NIM", "TensorRT-LLM"}
    assert len(session.exec(select(RecommendationRow)).all()) == 2
    # 2 lados × 2 techs = 4 evidências.
    assert len(session.exec(select(Evidence)).all()) == 4
