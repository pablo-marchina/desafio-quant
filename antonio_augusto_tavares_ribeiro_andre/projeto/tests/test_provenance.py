"""Testes da proveniência de scraping (F1.9).

Tudo **offline**: as funções puras (`content_hash`, `make_snippet`, `to_evidence`) não
tocam rede nem banco; a persistência (`record_evidence`) roda numa sessão SQLite isolada
(mesmo padrão de `test_db.py`). Provam o contrato do §8: um `FetchResult` (F1.7) vira uma
linha `evidence` com url/fetched_at/hash/snippet, ligada a uma entidade, com dedup
idempotente entre runs sobre a mesma fonte.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from packages.db.models import Company, Evidence
from packages.scraping import content_hash, make_snippet, record_evidence, to_evidence
from packages.scraping.router import FetchResult


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


def _company(session: Session) -> Company:
    company = Company(nome="Acme AI", setor="fintech")
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def test_content_hash_is_stable_under_whitespace() -> None:
    # Reformatação trivial (espaços/quebras) não muda o hash: normaliza antes de hashear.
    assert content_hash("conteúdo   da\n\n página") == content_hash("conteúdo da página")
    # Conteúdo diferente → hash diferente; é sha256 (64 hex).
    h = content_hash("outro conteúdo")
    assert h != content_hash("conteúdo da página")
    assert len(h) == 64


def test_make_snippet_returns_full_text_when_short() -> None:
    assert make_snippet("texto curto", max_chars=50) == "texto curto"
    # Whitespace é colapsado mesmo quando cabe inteiro.
    assert make_snippet("a   b\n c", max_chars=50) == "a b c"


def test_make_snippet_truncates_with_ellipsis_on_word_boundary() -> None:
    text = "palavra " * 100
    snippet = make_snippet(text, max_chars=40)
    assert snippet.endswith("…")
    assert not snippet.startswith("…")  # começou do início → sem reticência à esquerda
    assert "palavr…" not in snippet  # não corta no meio de um token


def test_make_snippet_centers_window_on_around_term() -> None:
    text = "ruído inicial " * 30 + " a startup usa RAG e embeddings " + "cauda " * 30
    snippet = make_snippet(text, around="RAG", max_chars=60)
    assert "RAG" in snippet
    assert snippet.startswith("…") and snippet.endswith("…")  # cortou dos dois lados


def test_to_evidence_builds_provenance_record() -> None:
    result = FetchResult(
        url="https://acme.ai/produto",
        text="A Acme usa RAG e embeddings para responder sobre documentos do cliente." * 10,
        title="Acme — Produto",
        strategy="firecrawl",
    )
    fetched = datetime(2026, 6, 3, tzinfo=UTC)
    ev = to_evidence(
        result,
        entity_type="company",
        entity_id=42,
        field="descricao",
        around="RAG",
        fetched_at=fetched,
    )
    assert ev.url == "https://acme.ai/produto"
    assert ev.fetched_at == fetched
    assert ev.content_hash == content_hash(result.text)
    assert ev.source_title == "Acme — Produto"
    assert ev.entity_type == "company" and ev.entity_id == 42 and ev.field == "descricao"
    assert "RAG" in ev.snippet


def test_to_evidence_rejects_empty_result() -> None:
    with pytest.raises(ValueError):
        to_evidence(
            FetchResult(url="https://x.example", text="   "),
            entity_type="company",
            entity_id=1,
        )


def test_record_evidence_persists_and_links(session: Session) -> None:
    company = _company(session)
    result = FetchResult(url="https://acme.ai/docs", text="100% via API externa, sem modelo.")
    ev = record_evidence(
        session, result, entity_type="company", entity_id=company.id, field="tecnologias"
    )
    session.commit()

    got = session.exec(
        select(Evidence).where(Evidence.entity_type == "company", Evidence.entity_id == company.id)
    ).one()
    assert got.id == ev.id
    assert got.url == "https://acme.ai/docs"
    assert got.content_hash is not None
    assert got.field == "tecnologias"


def test_record_evidence_dedups_same_source_and_target(session: Session) -> None:
    company = _company(session)
    result = FetchResult(url="https://acme.ai/docs", text="100% via API externa.")
    cid = company.id
    first = record_evidence(session, result, entity_type="company", entity_id=cid, field="x")
    second = record_evidence(session, result, entity_type="company", entity_id=cid, field="x")
    session.commit()

    assert first.id == second.id  # mesma url+hash+alvo → reaproveita a linha
    assert len(session.exec(select(Evidence)).all()) == 1


def test_record_evidence_keeps_distinct_targets(session: Session) -> None:
    company = _company(session)
    result = FetchResult(url="https://acme.ai/docs", text="mesmo conteúdo de fonte")
    record_evidence(session, result, entity_type="company", entity_id=company.id, field="a")
    record_evidence(session, result, entity_type="company", entity_id=company.id, field="b")
    session.commit()
    # Mesma fonte/conteúdo, mas campos distintos → duas evidências (dedup é por alvo).
    assert len(session.exec(select(Evidence)).all()) == 2
