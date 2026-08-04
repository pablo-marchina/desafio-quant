"""Testes da persistência de perfil (F1.10).

Offline: as funções de normalização e escopo são puras; o upsert roda numa sessão SQLite
isolada (mesmo padrão de `test_db.py`/`test_provenance.py`). Provam o contrato F1.10:
dedup idempotente por CNPJ > domínio > (nome, país), enriquecimento sem renomear, filtro
de escopo BR, e persistência da empresa com founders + evidência rastreável.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from packages.db.models import Company, Evidence, Founder
from packages.schemas.evidence import Claim
from packages.schemas.evidence import Evidence as EvidenceSchema
from packages.schemas.profile import Founder as FounderSchema
from packages.schemas.profile import StartupProfile, Technology
from packages.scraping import (
    br_scope,
    normalize_cnpj,
    normalize_domain,
    persist_profile,
    upsert_company,
    upsert_founder,
)

# CNPJ de teste válido (DVs corretos pelo módulo 11): 11.222.333/0001-81.
VALID_CNPJ = "11.222.333/0001-81"


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


def _ev(snippet: str = "trecho citável da fonte") -> EvidenceSchema:
    return EvidenceSchema(
        url="https://acme.com.br/sobre",
        snippet=snippet,
        fetched_at=datetime(2026, 6, 3, tzinfo=UTC),
        content_hash="abc123",
    )


# --- normalização (puro) ------------------------------------------------------


def test_normalize_domain_strips_scheme_www_path_and_case() -> None:
    assert normalize_domain("https://www.Acme.com.br/produto?x=1") == "acme.com.br"
    assert normalize_domain("acme.com.br") == "acme.com.br"
    assert normalize_domain("") is None
    assert normalize_domain(None) is None


def test_normalize_cnpj_validates_check_digits() -> None:
    assert normalize_cnpj(VALID_CNPJ) == "11222333000181"
    assert normalize_cnpj("11222333000181") == "11222333000181"  # já sem máscara
    assert normalize_cnpj("11.222.333/0001-99") is None  # DV errado
    assert normalize_cnpj("11111111111111") is None  # placeholder (tudo igual)
    assert normalize_cnpj("123") is None  # tamanho errado
    assert normalize_cnpj(None) is None


# --- escopo geográfico (Brasil) -----------------------------------------------


def test_br_scope_keeps_br_and_default() -> None:
    assert br_scope(StartupProfile(nome="Acme")).in_scope  # default pais=BR
    assert br_scope(StartupProfile(nome="Acme", pais="Brasil")).in_scope


def test_br_scope_filters_clearly_foreign() -> None:
    foreign = StartupProfile(nome="Acme Inc", pais="US", website="https://acme.com")
    verdict = br_scope(foreign)
    assert not verdict.in_scope
    assert "fora de escopo" in verdict.reason


def test_br_scope_keeps_foreign_pais_with_br_signal() -> None:
    # país não-BR, mas CNPJ válido (operação BR) → mantém.
    with_cnpj = StartupProfile(nome="Acme", pais="US", cnpj=Claim(value=VALID_CNPJ))
    assert br_scope(with_cnpj).in_scope
    # país não-BR, mas domínio .br → mantém.
    with_br_domain = StartupProfile(nome="Acme", pais="US", website="https://acme.com.br")
    assert br_scope(with_br_domain).in_scope


# --- upsert de company --------------------------------------------------------


def test_upsert_company_inserts_then_enriches(session: Session) -> None:
    p1 = StartupProfile(nome="Acme AI", website="https://acme.com.br")
    c1 = upsert_company(session, p1)
    assert c1.id is not None
    assert c1.domain == "acme.com.br"
    assert c1.pais == "BR"

    # Mesmo domínio, agora com setor → reaproveita a linha e enriquece.
    p2 = StartupProfile(
        nome="Acme AI", website="https://www.acme.com.br/", setor=Claim(value="fintech")
    )
    c2 = upsert_company(session, p2)
    assert c2.id == c1.id
    assert c2.setor == "fintech"
    assert len(session.exec(select(Company)).all()) == 1


def test_upsert_company_dedups_by_cnpj_across_domains(session: Session) -> None:
    p1 = StartupProfile(nome="Acme AI", website="https://acme.com.br", cnpj=Claim(value=VALID_CNPJ))
    c1 = upsert_company(session, p1)
    # Mesmo CNPJ, site diferente (rebrand) → mesma empresa (CNPJ tem precedência).
    p2 = StartupProfile(nome="Acme AI", website="https://acme.ai", cnpj=Claim(value=VALID_CNPJ))
    c2 = upsert_company(session, p2)
    assert c2.id == c1.id
    assert len(session.exec(select(Company)).all()) == 1


def test_upsert_company_does_not_rename_on_hit(session: Session) -> None:
    c1 = upsert_company(session, StartupProfile(nome="Acme AI", website="https://acme.com.br"))
    # Mesmo domínio, nome diferente → identidade estável, não renomeia.
    c2 = upsert_company(session, StartupProfile(nome="Acme Rebrand", website="https://acme.com.br"))
    assert c2.id == c1.id
    assert c2.nome == "Acme AI"


def test_upsert_company_falls_back_to_nome_pais(session: Session) -> None:
    # Sem domínio nem CNPJ → dedup fraco por (nome, país).
    c1 = upsert_company(session, StartupProfile(nome="Acme AI"))
    c2 = upsert_company(session, StartupProfile(nome="Acme AI", setor=Claim(value="saúde")))
    assert c2.id == c1.id
    assert c2.setor == "saúde"


# --- upsert de founder --------------------------------------------------------


def test_upsert_founder_dedups_by_name_and_linkedin(session: Session) -> None:
    company = upsert_company(session, StartupProfile(nome="Acme AI"))
    f1 = upsert_founder(session, company.id, FounderSchema(nome="Jane Doe", cargo="CEO"))
    # Mesmo nome (case-insensitive), agora com LinkedIn → mesma linha, enriquecida.
    f2 = upsert_founder(
        session,
        company.id,
        FounderSchema(nome="jane doe", linkedin_url="https://linkedin.com/in/janedoe"),
    )
    assert f2.id == f1.id
    assert f2.cargo == "CEO"
    assert f2.linkedin_url is not None
    assert len(session.exec(select(Founder)).all()) == 1


# --- persist_profile (orquestração) -------------------------------------------


def test_persist_profile_persists_company_founders_and_evidence(session: Session) -> None:
    profile = StartupProfile(
        nome="Acme AI",
        website="https://acme.com.br",
        cnpj=Claim(value=VALID_CNPJ, evidence=[_ev("CNPJ na Receita")]),
        descricao=Claim(value="copiloto de crédito", evidence=[_ev("o que faz")]),
        setor=Claim(value="fintech", evidence=[_ev("setor fintech")]),
        tecnologias=[Technology(nome="OpenAI API", categoria="LLM", evidence=[_ev("usa OpenAI")])],
        founders=[FounderSchema(nome="Jane Doe", cargo="CEO", evidence=[_ev("é CEO")])],
    )
    company = persist_profile(session, profile)
    session.commit()

    assert company is not None
    assert company.cnpj == "11222333000181"
    # Sub-estrutura rica com proveniência inline (design F0.6).
    assert company.tecnologias[0]["evidence"][0]["url"].startswith("https://acme.com.br")

    founders = session.exec(select(Founder).where(Founder.company_id == company.id)).all()
    assert len(founders) == 1 and founders[0].nome == "Jane Doe"

    # ≥3 evidências rastreáveis na tabela (cnpj + descricao + setor na company + founder).
    company_ev = session.exec(
        select(Evidence).where(Evidence.entity_type == "company", Evidence.entity_id == company.id)
    ).all()
    assert {e.field for e in company_ev} == {"cnpj", "descricao", "setor"}
    founder_ev = session.exec(select(Evidence).where(Evidence.entity_type == "founder")).all()
    assert len(founder_ev) == 1


def test_persist_founder_stamps_legal_basis(session: Session) -> None:
    # F1.13: toda evidência de founder carrega a base legal LGPD.
    profile = StartupProfile(
        nome="Acme AI",
        website="https://acme.com.br",
        founders=[FounderSchema(nome="Jane Doe", cargo="CEO", evidence=[_ev("é CEO")])],
    )
    company = persist_profile(session, profile)
    session.commit()
    founder_ev = session.exec(select(Evidence).where(Evidence.entity_type == "founder")).all()
    assert founder_ev and all(e.legal_basis == "legitimo_interesse" for e in founder_ev)
    # Evidência de company não recebe base legal (não é dado pessoal).
    company_ev = session.exec(
        select(Evidence).where(Evidence.entity_type == "company", Evidence.entity_id == company.id)
    ).all()
    assert all(e.legal_basis is None for e in company_ev)


def test_persist_drops_founder_with_sensitive_core(session: Session) -> None:
    # F1.13: founder com dado sensível no núcleo (cargo) não é coletado.
    profile = StartupProfile(
        nome="Acme AI",
        website="https://acme.com.br",
        founders=[
            FounderSchema(nome="Jane Doe", cargo="CEO", evidence=[_ev("é CEO")]),
            FounderSchema(nome="John Roe", cargo="CTO (evangélico)", evidence=[_ev("perfil")]),
        ],
    )
    company = persist_profile(session, profile)
    session.commit()
    founders = session.exec(select(Founder).where(Founder.company_id == company.id)).all()
    assert [f.nome for f in founders] == ["Jane Doe"]  # John Roe descartado
    # Sem founder persistido, não há evidência dele.
    assert len(session.exec(select(Evidence).where(Evidence.entity_type == "founder")).all()) == 1


def test_persist_redacts_founder_background(session: Session) -> None:
    profile = StartupProfile(
        nome="Acme AI",
        website="https://acme.com.br",
        founders=[
            FounderSchema(
                nome="Ana Lima",
                cargo="COO",
                background="Casada, 40 anos de idade. Líder de operações há 12 anos.",
                evidence=[_ev("bio")],
            )
        ],
    )
    company = persist_profile(session, profile)
    session.commit()
    founder = session.exec(select(Founder).where(Founder.company_id == company.id)).one()
    assert "[removido: LGPD]" in founder.background
    assert "Líder de operações" in founder.background


def test_persist_evidence_annotates_source_policy(session: Session) -> None:
    # F1.15: toda evidência carrega a decisão de ToS da fonte (site oficial → unlisted:allow).
    profile = StartupProfile(
        nome="Acme AI",
        website="https://acme.com.br",
        descricao=Claim(value="copiloto", evidence=[_ev("desc")]),
        founders=[FounderSchema(nome="Jane Doe", cargo="CEO", evidence=[_ev("é CEO")])],
    )
    persist_profile(session, profile)
    session.commit()
    rows = session.exec(select(Evidence)).all()
    assert rows and all(e.source_policy == "unlisted:allow" for e in rows)


def test_persist_profile_filters_out_of_scope(session: Session) -> None:
    foreign = StartupProfile(nome="Acme Inc", pais="US", website="https://acme.com")
    result = persist_profile(session, foreign)
    session.commit()
    assert result is None
    assert session.exec(select(Company)).all() == []


def test_persist_profile_is_idempotent(session: Session) -> None:
    profile = StartupProfile(
        nome="Acme AI",
        website="https://acme.com.br",
        descricao=Claim(value="copiloto", evidence=[_ev("desc")]),
    )
    first = persist_profile(session, profile)
    second = persist_profile(session, profile)
    session.commit()
    assert first.id == second.id
    assert len(session.exec(select(Company)).all()) == 1
    # Evidência não duplica entre runs sobre a mesma fonte/alvo.
    assert len(session.exec(select(Evidence)).all()) == 1
