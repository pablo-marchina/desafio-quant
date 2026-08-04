"""Testes da camada semântica do chat de descoberta (F3.10/F5.12 — cohort-RAG).

Cobre: a detecção de sinal semântico (`residual_query`), o ranking por similaridade em memória
(offline/determinístico, sobre o `HashingEmbedder`), a anexação de citação por empresa resolvendo
o polimorfismo da `evidence`, e a degradação para o modo só-filtro sem texto livre. Sessão SQLite
isolada, mesmo padrão dos demais testes.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from packages.agents.cohort_rag import (
    load_company_evidence,
    rank_discovery,
)
from packages.agents.discovery import residual_query
from packages.db.models import Company, Evidence, Score
from packages.db.models import Recommendation as RecommendationRow
from packages.schemas.enums import Classification, Complexity, Priority

# --- detecção de sinal semântico (puro) --------------------------------------


@pytest.mark.parametrize(
    "pergunta",
    [
        "Quais startups tem gap de inferencia?",  # 100% intenção de inferência → filtro
        "AI-native maduras",  # classe + maturidade → filtro
        "Quem e candidata a TensorRT?",  # tag NVIDIA → filtro
        "AIMI acima de 40",  # piso de AIMI → filtro
        "me mostra a coorte",  # genérico → filtro
    ],
)
def test_residual_vazio_para_pergunta_de_filtro(pergunta: str) -> None:
    assert residual_query(pergunta) == ""


@pytest.mark.parametrize(
    ("pergunta", "termo"),
    [
        ("startups de deteccao de fraude", "fraude"),
        ("quem trabalha com visao computacional no varejo", "varejo"),
        ("healthtech AI-native propensas a NIM", "healthtech"),  # texto livre + filtros
        ("agronegocio com gap de inferencia", "agronegocio"),
    ],
)
def test_residual_capta_texto_livre(pergunta: str, termo: str) -> None:
    assert termo in residual_query(pergunta).split()


# --- integração: ranking + citação -------------------------------------------


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _company(
    session: Session,
    *,
    nome: str,
    setor: str,
    descricao: str,
    ip: int,
    cls: Classification = Classification.AI_NATIVE,
) -> int:
    c = Company(
        nome=nome, domain=f"{nome.lower()}.com", pais="BR", setor=setor, descricao=descricao
    )
    session.add(c)
    session.flush()
    score = Score(
        company_id=c.id, run_id="r1", classificacao=cls, total=55,
        data_moat=20, workflow_depth=17, technical_optimization=6, distribution_moat=12,
        inception_priority=ip,
    )
    session.add(score)
    session.flush()
    # Evidência ligada ao score (pilar) — o caminho polimórfico mais comum (§8).
    session.add(
        Evidence(
            url=f"https://{nome.lower()}.com/sobre", snippet=descricao, fetched_at=datetime.now(),
            entity_type="score", entity_id=score.id, field="data_moat", source_title=nome,
        )
    )
    session.flush()
    return c.id


def test_modo_semantico_reordena_por_relevancia(session: Session) -> None:
    # Prioridade poria a "irrelevante" (LogiCo, ip=90) no topo; a semântica deve subir a de fraude.
    fraude = _company(
        session, nome="FraudeIA", setor="Fintech",
        descricao="deteccao de fraude em pagamentos com modelos de risco", ip=10,
    )
    _company(
        session, nome="LogiCo", setor="Logistica",
        descricao="otimizacao de rotas de entrega para transportadoras", ip=90,
    )

    # Candidatos na ordem de prioridade (LogiCo primeiro), como o filtro a montante entrega.
    cand = _ids_by_priority(session)
    ranking = rank_discovery(session, "startups de deteccao de fraude", cand)

    assert ranking.modo == "semantico"
    assert ranking.hits[0].company_id == fraude  # subiu apesar da prioridade menor
    assert ranking.hits[0].similaridade is not None
    assert ranking.hits[0].similaridade >= ranking.hits[1].similaridade


def test_modo_filtro_preserva_ordem_de_prioridade(session: Session) -> None:
    a = _company(session, nome="Alpha", setor="Fintech", descricao="pagamentos", ip=90)
    b = _company(session, nome="Beta", setor="Fintech", descricao="credito", ip=10)

    # "AI-native" é filtro puro (sem resíduo) → mantém a ordem recebida (prioridade).
    ranking = rank_discovery(session, "AI-native", [a, b])

    assert ranking.modo == "filtro"
    assert [h.company_id for h in ranking.hits] == [a, b]
    assert all(h.similaridade is None for h in ranking.hits)


def test_hit_carrega_citacao_real(session: Session) -> None:
    cid = _company(
        session, nome="FraudeIA", setor="Fintech",
        descricao="deteccao de fraude em pagamentos", ip=50,
    )
    ranking = rank_discovery(session, "startups de fraude", [cid])

    hit = ranking.hits[0]
    assert hit.citacao is not None
    assert hit.citacao.url == "https://fraudeia.com/sobre"
    assert "fraude" in hit.citacao.snippet


def test_lista_vazia_degrada_limpo(session: Session) -> None:
    ranking = rank_discovery(session, "qualquer coisa", [])
    assert ranking.modo == "filtro"
    assert ranking.hits == []


def test_load_company_evidence_resolve_polimorfismo(session: Session) -> None:
    cid = _company(
        session, nome="Acme", setor="SaaS", descricao="plataforma B2B", ip=30,
    )
    # Recomendação + evidência do lado NVIDIA, para exercitar o caminho 'recommendation'.
    rec = RecommendationRow(
        company_id=cid, run_id="r1", tech="NVIDIA NIM",
        justificativa_tecnica="serving", justificativa_negocio="custo",
        prioridade=Priority.ALTA, complexidade=Complexity.MEDIA, proxima_acao="testar",
    )
    session.add(rec)
    session.flush()
    session.add(
        Evidence(
            url="https://docs.nvidia.com/nim", snippet="NIM serving otimizado",
            fetched_at=datetime.now(), entity_type="recommendation", entity_id=rec.id,
            field="nvidia",
        )
    )
    session.flush()

    evid = load_company_evidence(session)
    urls = {c.url for c in evid[cid]}
    assert "https://acme.com/sobre" in urls  # via score
    assert "https://docs.nvidia.com/nim" in urls  # via recommendation


def _ids_by_priority(session: Session) -> list[int]:
    from apps.api.companies import list_companies

    return [c.id for c in list_companies(session)]
