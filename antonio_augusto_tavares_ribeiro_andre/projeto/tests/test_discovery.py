"""Testes do motor do chat de descoberta da coorte (F3.10/F5.12).

Cobre o parser de intenção (`parse_query`, puro/offline) e a integração ponta a ponta
pergunta → filtro → `list_companies` numa sessão SQLite isolada (mesmo padrão dos demais).
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from apps.api.companies import list_companies
from packages.agents.discovery import CohortQuery, parse_query, summarize
from packages.db.models import Company, Score
from packages.db.models import Recommendation as RecommendationRow
from packages.schemas.enums import Classification, Complexity, Priority

# --- parser de intenção (puro) -----------------------------------------------


@pytest.mark.parametrize(
    ("pergunta", "campo", "esperado"),
    [
        ("quais são mais propensas a precisar de NIM?", "nvidia_tech", "NIM"),
        ("startups candidatas a TensorRT", "nvidia_tech", "TensorRT-LLM"),
        ("quem se beneficiaria de Triton", "nvidia_tech", "Triton"),
        ("as com gap de inferência", "nvidia_tech", "NIM"),  # intenção → família de inferência
        ("propensas a graduar da API pra stack otimizada", "nvidia_tech", "NIM"),
        ("startups AI-native", "classificacao", "AI-native"),
        ("empresas non-AI", "classificacao", "non-AI"),
    ],
)
def test_parse_query_capta_intencao(pergunta: str, campo: str, esperado: str) -> None:
    assert getattr(parse_query(pergunta), campo) == esperado


def test_parse_query_aimi_threshold() -> None:
    assert parse_query("as mais maduras").min_aimi == 50
    assert parse_query("startups com AIMI >= 40").min_aimi == 40
    assert parse_query("AIMI acima de 70").min_aimi == 70


def test_parse_query_combina_filtros() -> None:
    q = parse_query("healthtech AI-native propensas a NIM com AIMI acima de 30")
    assert q.classificacao == "AI-native"
    assert q.nvidia_tech == "NIM"
    assert q.min_aimi == 30
    assert "AI-native" in q.entendido and "NIM" in q.entendido


def test_parse_query_tag_especifica_vence_intencao() -> None:
    # menção explícita a Triton não deve ser sobrescrita pelo proxy de inferência → NIM.
    assert parse_query("quem precisa de Triton pra serving").nvidia_tech == "Triton"


def test_parse_query_vazia_sem_filtro() -> None:
    q = parse_query("me mostra a coorte")
    assert q == CohortQuery(entendido=q.entendido)  # nenhum filtro setado
    assert q.nvidia_tech is None and q.classificacao is None and q.min_aimi is None


def test_summarize_conta_e_explica() -> None:
    frase = summarize(parse_query("propensas a NIM"), 3)
    assert "3 startups" in frase and "NIM" in frase and "Inception Priority" in frase


# --- integração pergunta → filtro → empresas ---------------------------------


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _company_with_rec(
    session: Session, *, nome: str, cls: Classification, tech: str | None, ip: int
) -> None:
    c = Company(nome=nome, domain=f"{nome.lower()}.com", pais="BR", setor="HealthTech")
    session.add(c)
    session.flush()
    session.add(
        Score(
            company_id=c.id, run_id="r1", classificacao=cls, total=55,
            data_moat=20, workflow_depth=17, technical_optimization=6, distribution_moat=12,
            inception_priority=ip,
        )
    )
    if tech is not None:
        session.add(
            RecommendationRow(
                company_id=c.id, run_id="r1", tech=tech,
                justificativa_tecnica="serving otimizado", justificativa_negocio="reduz custo",
                prioridade=Priority.ALTA, complexidade=Complexity.MEDIA, proxima_acao="testar",
            )
        )
    session.flush()


def test_discover_retorna_so_as_suscetiveis_a_nim(session: Session) -> None:
    AIN, NAI = Classification.AI_NATIVE, Classification.NON_AI
    _company_with_rec(session, nome="GraduaIA", cls=AIN, tech="NVIDIA NIM", ip=80)
    _company_with_rec(session, nome="WrapCo", cls=AIN, tech="NeMo Guardrails", ip=40)
    _company_with_rec(session, nome="LojaApp", cls=NAI, tech=None, ip=10)

    q = parse_query("quais são mais propensas a precisar de NIM?")
    empresas = list_companies(session, nvidia_tech=q.nvidia_tech)

    assert [e.nome for e in empresas] == ["GraduaIA"]  # só a que tem NIM recomendado
    assert empresas[0].inception_priority == 80
