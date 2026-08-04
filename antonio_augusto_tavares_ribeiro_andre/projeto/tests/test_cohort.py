"""Testes do cohort builder (F1.14).

Offline: a extração de candidatas (`candidate_domains`) é pura e o laço (`build_cohort`)
roda com `runner`/`crawl_fn` injetados + SQLite isolado (mesmo padrão de
`test_recommendation_persistence.py`/`test_score_persistence.py`) — sem rede nem Twisted.
Provam o contrato F1.14: links de saída do crawl viram fila de candidatas; o lote perfila
cada uma, acumula na `company` (perfil+score+recomendações), aplica a política auto-HITL
(baixa confiança / fora de escopo → revisão, não bloqueia) e continua em erro.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from packages.agents.cohort import (
    CohortCandidate,
    build_cohort,
    candidate_domains,
    candidates_from_seed,
    discover_candidates,
)
from packages.db.models import Company
from packages.db.models import Recommendation as RecommendationRow
from packages.db.models import Score as ScoreRow
from packages.schemas.aimi import AIMIScore, PillarScore
from packages.schemas.enums import (
    AIMIPillar,
    Classification,
    Complexity,
    ExecutionMode,
    HITLMode,
    Priority,
    RunStatus,
)
from packages.schemas.evidence import Evidence as EvidenceSchema
from packages.schemas.profile import StartupProfile
from packages.schemas.recommendation import Recommendation
from packages.schemas.state import GraphState, RawDocument
from packages.scraping.crawler import CrawledPage
from packages.scraping.soup import Link

# --- candidate_domains (puro, offline) ---------------------------------------


def _page(url: str, links: list[tuple[str, str]], *, source_id: str = "prog") -> CrawledPage:
    return CrawledPage(url=url, links=tuple(Link(u, t) for u, t in links), source_id=source_id)


def test_candidate_domains_extracts_external_company_links() -> None:
    pages = [
        _page(
            "https://program.org/portfolio",
            [
                ("https://acme.ai/", "Acme AI"),
                ("https://www.beta.com.br/sobre", "Beta"),
                ("https://program.org/sobre", "link interno do portfólio"),
                ("https://twitter.com/acme", "social"),
                ("https://acme.ai/time", "domínio repetido"),
            ],
        )
    ]
    cands = candidate_domains(pages, seed_hosts=["program.org"])

    assert [c.domain for c in cands] == ["acme.ai", "beta.com.br"]  # dedup + sem interno/social
    assert cands[0].query == "https://acme.ai"
    assert cands[0].name == "Acme AI"
    assert cands[0].source_id == "prog"


def test_candidate_domains_excludes_seed_subdomains_and_no_host() -> None:
    pages = [
        _page(
            "https://seed.com/lista",
            [
                ("https://blog.seed.com/post", "subdomínio da seed"),
                ("mailto:contato@x.com", "sem host"),
                ("https://realstartup.io/", "Real"),
            ],
            source_id="news",
        )
    ]
    cands = candidate_domains(pages, seed_hosts=["seed.com"])

    assert [c.domain for c in cands] == ["realstartup.io"]


def test_discover_candidates_uses_injected_crawl_and_sources() -> None:
    from packages.scraping.seeds import Source

    src = Source(
        id="prog", name="Prog", url="https://program.org", type="program",
        country="BR", policy="allow", robots="allow", tos_scraping="permitted", legal_basis="x",
    )
    pages = [_page("https://program.org/portfolio", [("https://acme.ai/", "Acme")])]

    cands = discover_candidates(sources=[src], crawl_fn=lambda srcs, **kw: pages)

    assert [c.domain for c in cands] == ["acme.ai"]


def test_candidates_from_seed_reads_curated_yaml(tmp_path) -> None:
    import yaml

    seed = tmp_path / "cohort_candidates.yaml"
    seed.write_text(
        yaml.safe_dump(
            {"candidates": [
                {"name": "Hand Talk", "query": "Hand Talk Libras IA"}, {"name": "Kunumi"},
            ]},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    cands = candidates_from_seed(seed)

    assert [c.name for c in cands] == ["Hand Talk", "Kunumi"]
    assert cands[0].query == "Hand Talk Libras IA"
    assert cands[0].domain == "hand-talk"  # slug do nome (domínio real vem do perfil)
    assert cands[1].query == "Kunumi"  # query default = nome
    assert all(c.source_id == "cohort-seed" for c in cands)


def test_real_candidate_seed_loads() -> None:
    # A seed versionada do projeto carrega e tem candidatas reais.
    cands = candidates_from_seed()
    assert len(cands) >= 5
    assert all(c.name and c.query for c in cands)


# --- build_cohort (lote, SQLite isolado) -------------------------------------


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return lambda: Session(engine)


def _ev(url: str = "https://acme.com.br/x", snippet: str = "sinal citável") -> EvidenceSchema:
    return EvidenceSchema(
        url=url, snippet=snippet, fetched_at=datetime(2026, 6, 1, tzinfo=UTC), content_hash="h0"
    )


def _pillar(pilar: AIMIPillar, score: int, *, ev: bool = True) -> PillarScore:
    return PillarScore(
        pilar=pilar, score=score, justificativa=f"cálculo de {pilar.value}",
        evidencia=[_ev()] if ev else [],
    )


def _aimi(classificacao: Classification = Classification.AI_NATIVE) -> AIMIScore:
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, 18),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, 16),
        technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, 5, ev=False),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, 12),
        classificacao=classificacao,
    )


def _rec(tech: str = "NVIDIA NIM") -> Recommendation:
    return Recommendation(
        tech=tech, justificativa_tecnica="serving otimizado", justificativa_negocio="reduz custo",
        prioridade=Priority.ALTA, complexidade=Complexity.MEDIA, proxima_acao="testar NIM",
        pilar_origem=AIMIPillar.TECHNICAL_OPTIMIZATION,
        evidencia_gap=[_ev("https://acme.com.br/p", "100% via API")],
        evidencia_nvidia=[_ev("https://build.nvidia.com/nim", "NIM otimizado")],
    )


def _state(
    *,
    run_id: str = "r1",
    website: str = "https://acme.com.br",
    pais: str = "BR",
    nome: str = "Acme AI",
    profile: bool = True,
    status: RunStatus = RunStatus.COMPLETED,
    needs_review: bool = False,
) -> GraphState:
    return GraphState(
        run_id=run_id, query=website, mode=ExecutionMode.SINGLE_COMPANY,
        status=status, needs_review=needs_review,
        profile=StartupProfile(nome=nome, pais=pais, website=website) if profile else None,
        aimi=_aimi() if profile else None,
        recommendations=[_rec()] if profile else [],
        raw_docs=[
            RawDocument(
                url=website, content="doc", fetched_at=datetime(2026, 6, 1, tzinfo=UTC)
            )
        ],
    )


def _runner(states: dict[str, GraphState | Exception], calls: list | None = None):
    def runner(query, *, mode, hitl):  # noqa: ANN001, ANN202 — espelha run_pipeline
        if calls is not None:
            calls.append((query, mode, hitl))
        result = states[query]
        if isinstance(result, Exception):
            raise result
        return result

    return runner


def test_build_cohort_persists_profiled_company(session_factory, engine) -> None:
    cand = CohortCandidate(domain="acme.com.br", query="https://acme.com.br", name="Acme")
    calls: list = []
    report = build_cohort(
        [cand], session_factory=session_factory,
        runner=_runner({"https://acme.com.br": _state()}, calls),
    )

    assert report.total == 1
    [out] = report.persisted
    assert out.company_id is not None
    assert out.evidence_count == 1
    # hitl=AUTO é a política travada do lote (não bloqueia).
    assert calls == [("https://acme.com.br", ExecutionMode.SINGLE_COMPANY, HITLMode.AUTO)]

    with Session(engine) as s:
        assert s.exec(select(Company)).one().nome == "Acme AI"
        assert s.exec(select(ScoreRow)).one().classificacao is Classification.AI_NATIVE
        assert s.exec(select(RecommendationRow)).one().tech == "NVIDIA NIM"


def test_build_cohort_out_of_scope_not_persisted(session_factory, engine) -> None:
    cand = CohortCandidate(domain="acme.com", query="https://acme.com")
    report = build_cohort(
        [cand], session_factory=session_factory,
        runner=_runner({"https://acme.com": _state(website="https://acme.com", pais="US")}),
    )

    [out] = report.outcomes
    assert not out.persisted
    assert out.needs_review
    assert out.status is RunStatus.OUT_OF_SCOPE
    assert out in report.needs_review
    assert not report.errored  # fora de escopo é resultado legítimo, não erro
    with Session(engine) as s:
        assert s.exec(select(Company)).all() == []


def test_build_cohort_no_profile_marks_review(session_factory) -> None:
    cand = CohortCandidate(domain="x.com.br", query="https://x.com.br")
    report = build_cohort(
        [cand], session_factory=session_factory,
        runner=_runner(
            {"https://x.com.br": _state(profile=False, status=RunStatus.INSUFFICIENT_DATA)}
        ),
    )

    [out] = report.outcomes
    assert not out.persisted
    assert out.needs_review
    assert not report.errored


def test_build_cohort_continues_on_error(session_factory, engine) -> None:
    bad = CohortCandidate(domain="bad.com.br", query="https://bad.com.br")
    good = CohortCandidate(domain="good.com.br", query="https://good.com.br")
    report = build_cohort(
        [bad, good], session_factory=session_factory,
        runner=_runner(
            {
                "https://bad.com.br": RuntimeError("boom"),
                "https://good.com.br": _state(website="https://good.com.br", nome="Good"),
            }
        ),
    )

    assert [o.domain for o in report.errored] == ["bad.com.br"]
    assert [o.domain for o in report.persisted] == ["good.com.br"]
    with Session(engine) as s:
        assert s.exec(select(Company)).one().nome == "Good"  # o erro não derrubou o lote


def test_build_cohort_respects_limit(session_factory) -> None:
    cands = [
        CohortCandidate(domain=f"c{i}.com.br", query=f"https://c{i}.com.br") for i in range(3)
    ]
    calls: list = []
    states = {
        f"https://c{i}.com.br": _state(run_id=f"r{i}", website=f"https://c{i}.com.br", nome=f"C{i}")
        for i in range(3)
    }
    report = build_cohort(
        cands, session_factory=session_factory, runner=_runner(states, calls), limit=2
    )

    assert report.total == 2
    assert len(calls) == 2
