"""Testes da ponte coorte real → eval set (F7.1).

Offline, numa sessão SQLite isolada (mesmo padrão de `test_score_persistence.py`): monta
`company` + `score` + `recommendation` + `evidence` e prova que `entry_from_company` deriva a
região coerente, puxa techs e `evidence_urls` reais, marca `label_source='model'`, e **pula**
o que não fecha (sem score / região não-canônica) em vez de poluir o set. Também cobre
`derive_region` (puro) e o round-trip do YAML pelos validadores do `LabeledStartup`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from packages.db.models import Company, Evidence, Score
from packages.db.models import Recommendation as RecommendationRow
from packages.eval.cohort_to_eval import (
    cohort_entries,
    derive_region,
    dump_entries,
    entry_from_company,
)
from packages.eval.dataset import EVAL_DIR, ExpectedPillars, LabeledStartup, load_eval_set
from packages.schemas.enums import Classification, Complexity, PlaneRegion, Priority


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _company(
    session: Session, *, nome: str, domain: str, descricao: str = "produto de IA"
) -> Company:
    c = Company(
        nome=nome, domain=domain, website=f"https://{domain}", descricao=descricao,
        setor="HealthTech", pais="BR",
    )
    session.add(c)
    session.flush()
    return c


def _score(
    session: Session, company_id: int, *,
    cls: Classification = Classification.AI_NATIVE,
    dm: int = 20, wf: int = 17, to: int = 6, dist: int = 12,
) -> Score:
    s = Score(
        company_id=company_id, run_id="r1", classificacao=cls, total=dm + wf + to + dist,
        data_moat=dm, workflow_depth=wf, technical_optimization=to, distribution_moat=dist,
        just_data_moat="dataset clínico proprietário",
    )
    session.add(s)
    session.flush()
    return s


def _rec(session: Session, company_id: int, tech: str) -> None:
    session.add(
        RecommendationRow(
            company_id=company_id, run_id="r1", tech=tech,
            justificativa_tecnica="serving otimizado", justificativa_negocio="reduz custo",
            prioridade=Priority.ALTA, complexidade=Complexity.MEDIA, proxima_acao="testar",
        )
    )
    session.flush()


def _ev(
    session: Session, entity_type: str, entity_id: int, url: str, *, field: str = "descricao"
) -> None:
    session.add(
        Evidence(
            url=url, snippet="trecho citável", fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
            entity_type=entity_type, entity_id=entity_id, field=field,
        )
    )
    session.flush()


# --- derive_region (puro) ----------------------------------------------------


def _p(dm: int, wf: int, to: int, dist: int) -> ExpectedPillars:
    return ExpectedPillars(
        data_moat=dm, workflow_depth=wf, technical_optimization=to, distribution_moat=dist
    )


def test_derive_region_maps_pillars_to_plane() -> None:
    AIN, AIE, NAI = Classification.AI_NATIVE, Classification.AI_ENABLED, Classification.NON_AI
    assert derive_region(NAI, _p(4, 3, 1, 9)) is PlaneRegion.FORA_ESCOPO
    assert derive_region(AIE, _p(7, 6, 5, 16)) is PlaneRegion.PERIFERICO
    # alvo_graduação ★: P3 baixo (≤8) + P1/P2 estabelecido (≥13).
    assert derive_region(AIN, _p(20, 17, 6, 12)) is PlaneRegion.ALVO_GRADUACAO
    # maduro: P3 estabelecido (≥13).
    assert derive_region(AIN, _p(20, 18, 19, 20)) is PlaneRegion.MADURO
    # wrapper: P3 baixo + P1/P2 baixo.
    assert derive_region(AIN, _p(3, 5, 3, 6)) is PlaneRegion.WRAPPER
    # incoerente: AI-native com P3 emergente (9–12) → sem região canônica.
    assert derive_region(AIN, _p(20, 17, 10, 12)) is None


# --- entry_from_company ------------------------------------------------------


def test_entry_from_company_builds_real_label(session: Session) -> None:
    c = _company(session, nome="RadiologIA", domain="radiologia.com.br")
    s = _score(session, c.id, dm=20, wf=17, to=6, dist=12)
    _rec(session, c.id, "NVIDIA NIM")
    _rec(session, c.id, "Triton")
    _ev(session, "company", c.id, "https://radiologia.com.br/sobre")
    _ev(session, "score", s.id, "https://news.com/radiologia", field="data_moat")
    _ev(session, "score", s.id, "https://build.nvidia.com/nim", field="data_moat")  # KB → excluída

    entry, reason = entry_from_company(session, c)

    assert reason is None
    assert entry is not None
    assert entry.label_source == "model"
    assert entry.synthetic is False
    assert entry.region is PlaneRegion.ALVO_GRADUACAO
    assert entry.expected_nvidia_techs == ["NVIDIA NIM", "Triton"]
    assert "https://radiologia.com.br/sobre" in entry.evidence_urls
    assert "https://news.com/radiologia" in entry.evidence_urls
    assert all("nvidia.com" not in u for u in entry.evidence_urls)  # KB filtrada
    assert entry.id == "real-radiologia.com.br"


def test_entry_skips_when_no_score(session: Session) -> None:
    c = _company(session, nome="NoScore", domain="noscore.com.br")
    entry, reason = entry_from_company(session, c)
    assert entry is None
    assert "score" in reason


def test_entry_skips_incoherent_region(session: Session) -> None:
    c = _company(session, nome="Emergente", domain="emergente.com.br")
    _score(session, c.id, to=10)  # AI-native com P3 emergente → sem região
    entry, reason = entry_from_company(session, c)
    assert entry is None
    assert "região" in reason


def test_evidence_falls_back_to_website(session: Session) -> None:
    c = _company(session, nome="SemEv", domain="semev.com.br")
    _score(session, c.id, dm=20, wf=17, to=6, dist=12)
    entry, _ = entry_from_company(session, c)
    assert entry.evidence_urls == ["https://semev.com.br"]


def test_cohort_entries_and_yaml_round_trip(session: Session) -> None:
    good = _company(session, nome="RoundTrip", domain="rt.com.br")
    _score(session, good.id, dm=20, wf=17, to=6, dist=12)
    _ev(session, "company", good.id, "https://rt.com.br/sobre")
    _company(session, nome="NoScore", domain="noscore.com.br")  # sem score → pulada

    entries, skipped = cohort_entries(session)

    assert [e.id for e in entries] == ["real-rt.com.br"]
    assert [domain for domain, _ in skipped] == ["noscore.com.br"]

    # O YAML emitido recarrega e passa pelos validadores do LabeledStartup.
    [raw] = yaml.safe_load(dump_entries(entries))["entries"]
    reloaded = LabeledStartup.model_validate(raw)
    assert reloaded.id == "real-rt.com.br"
    assert reloaded.label_source == "model"
    assert reloaded.synthetic is False


def _raw_entry(eid: str, *, source: str, synthetic: bool, **extra) -> dict:
    # wrapper coerente (AI-native, P3 baixo, P1/P2 baixo) — passa nos validadores.
    return {
        "id": eid, "nome": eid, "setor": "X", "descricao": "d",
        "classificacao": "AI-native", "region": "wrapper",
        "aimi": {
            "data_moat": 3, "workflow_depth": 5, "technical_optimization": 3, "distribution_moat": 6
        },
        "rationale": "r", "synthetic": synthetic, "label_source": source, **extra,
    }


def test_load_eval_set_excludes_model_by_default(monkeypatch, tmp_path) -> None:
    import packages.eval.dataset as dataset

    entries = [
        _raw_entry("h1", source="human", synthetic=True),
        _raw_entry("m1", source="model", synthetic=False, evidence_urls=["https://m1.com.br"]),
    ]
    (tmp_path / "set.yaml").write_text(
        yaml.safe_dump({"entries": entries}, allow_unicode=True), encoding="utf-8"
    )
    monkeypatch.setattr(dataset, "EVAL_DIR", tmp_path)
    dataset.load_eval_set.cache_clear()
    try:
        assert [e.id for e in dataset.load_eval_set()] == ["h1"]  # headline = só human
        assert {e.id for e in dataset.load_eval_set(include_model=True)} == {"h1", "m1"}
    finally:
        dataset.load_eval_set.cache_clear()  # não vaza o tmp p/ outros testes


def test_real_eval_dir_is_clean_for_other_tests() -> None:
    # Sanidade: o EVAL_DIR real continua carregando (não quebrado pelo monkeypatch acima).
    assert EVAL_DIR.exists()
    assert len(load_eval_set()) >= 20
