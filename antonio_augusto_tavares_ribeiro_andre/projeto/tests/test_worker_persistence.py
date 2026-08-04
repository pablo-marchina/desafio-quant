"""Testes da persistência pós-run do worker (F2.10 — fecha o run e2e → tabelas F0.6).

Offline, numa sessão SQLite isolada (mesmo padrão de `test_score_persistence.py`/
`test_recommendation_persistence.py`). Provam o contrato de `apps/worker/persistence.py`: lido o
`GraphState` final, o run inteiro materializa em `run`/`company`/`score`/`recommendation` (cada
um com sua evidência polimórfica), numa transação só, idempotente, e degradando sem alucinar
(fora de escopo / sem perfil gravam **só** a linha `run`). Cobre também o wiring no
`run_graph_job` (sessão injetada → as linhas aparecem após o job).
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from apps.worker import run_graph_job
from apps.worker.persistence import persist_run_state, upsert_run
from packages.db.models import Company, Evidence, Run
from packages.db.models import Recommendation as RecommendationRow
from packages.db.models import Score as ScoreRow
from packages.schemas import (
    AIMIPillar,
    AIMIScore,
    Briefing,
    BriefingStatus,
    Classification,
    Complexity,
    ExecutionMode,
    GraphState,
    HITLMode,
    PillarScore,
    Priority,
    Recommendation,
    RunStatus,
    StartupProfile,
)
from packages.schemas.evidence import Claim
from packages.schemas.evidence import Evidence as EvidenceSchema


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


# --- builders -----------------------------------------------------------------


def _ev(url: str, snippet: str) -> EvidenceSchema:
    return EvidenceSchema(
        url=url,
        snippet=snippet,
        fetched_at=datetime(2026, 6, 1, tzinfo=UTC),
        content_hash=f"hash-{snippet[:8]}",
    )


def _pillar(pilar: AIMIPillar, score: int, *, ev: bool = True) -> PillarScore:
    evidencia = [_ev(f"https://acme.com.br/{pilar.value}", f"sinal de {pilar.value}")] if ev else []
    return PillarScore(
        pilar=pilar, score=score, justificativa=f"cálculo de {pilar.value}", evidencia=evidencia
    )


def _aimi() -> AIMIScore:
    return AIMIScore(
        data_moat=_pillar(AIMIPillar.DATA_MOAT, 18),
        workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, 20),
        technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, 5, ev=False),
        distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, 12),
        classificacao=Classification.AI_NATIVE,
        confidence=0.9,
        inception_priority=72,
        heuristic_version="v1",
    )


def _rec(tech: str = "NVIDIA NIM") -> Recommendation:
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
    )


def _profile(*, pais: str = "BR", website: str | None = None) -> StartupProfile:
    return StartupProfile(
        nome="Acme AI",
        pais=pais,
        website=website,
        descricao=Claim[str](
            value="copiloto de IA para jurídico",
            evidence=[_ev("https://acme.com.br/sobre", "copiloto de IA para jurídico")],
        ),
    )


def _state(
    *,
    run_id: str = "run-1",
    status: RunStatus = RunStatus.COMPLETED,
    profile: StartupProfile | None = None,
    aimi: AIMIScore | None = None,
    recommendations: list[Recommendation] | None = None,
    briefing: Briefing | None = None,
) -> GraphState:
    return GraphState(
        run_id=run_id,
        query="Acme AI",
        status=status,
        profile=profile if profile is not None else _profile(),
        aimi=aimi if aimi is not None else _aimi(),
        recommendations=recommendations if recommendations is not None else [_rec()],
        briefing=briefing,
    )


# --- persist_run_state (orquestração) -----------------------------------------


def test_materializes_full_run(session: Session) -> None:
    persist_run_state(session, _state())
    session.commit()

    run = session.get(Run, "run-1")
    assert run is not None and run.status is RunStatus.COMPLETED

    company = session.exec(select(Company)).one()
    assert company.nome == "Acme AI" and company.run_id == "run-1"

    score = session.exec(select(ScoreRow)).one()
    assert score.company_id == company.id and score.run_id == "run-1"
    assert score.classificacao is Classification.AI_NATIVE
    assert score.total == 18 + 20 + 5 + 12

    rec = session.exec(select(RecommendationRow)).one()
    assert rec.company_id == company.id and rec.tech == "NVIDIA NIM"

    # Evidência polimórfica das 3 entidades ligada (§8): company + score + rec (2 lados).
    types = {e.entity_type for e in session.exec(select(Evidence)).all()}
    assert types == {"company", "score", "recommendation"}
    rec_sides = {
        e.field
        for e in session.exec(
            select(Evidence).where(Evidence.entity_type == "recommendation")
        ).all()
    }
    assert rec_sides == {"gap", "nvidia"}


def test_is_idempotent_across_reprocess(session: Session) -> None:
    # Reprocessa o mesmo run (ex.: retry/resume do worker) → enriquece, não duplica.
    persist_run_state(session, _state())
    persist_run_state(session, _state())
    session.commit()

    assert len(session.exec(select(Run)).all()) == 1
    assert len(session.exec(select(Company)).all()) == 1
    assert len(session.exec(select(ScoreRow)).all()) == 1
    assert len(session.exec(select(RecommendationRow)).all()) == 1


def test_out_of_scope_profile_writes_only_run(session: Session) -> None:
    # Perfil claramente estrangeiro (país não-BR, sem CNPJ nem domínio .br) → F2.13.
    foreign = StartupProfile(nome="Foreign Inc", pais="US", website="https://foreign.com")
    persist_run_state(
        session, _state(status=RunStatus.OUT_OF_SCOPE, profile=foreign, recommendations=[])
    )
    session.commit()

    assert session.get(Run, "run-1") is not None
    assert session.exec(select(Company)).all() == []  # fora de escopo não materializa company
    assert session.exec(select(ScoreRow)).all() == []
    assert session.exec(select(RecommendationRow)).all() == []


def test_no_profile_writes_only_run(session: Session) -> None:
    # Espinha offline / "dados insuficientes" (F2.12): sem perfil, grava só a linha run.
    state = GraphState(run_id="run-1", query="Acme AI", status=RunStatus.INSUFFICIENT_DATA)
    persist_run_state(session, state)
    session.commit()

    run = session.get(Run, "run-1")
    assert run is not None and run.status is RunStatus.INSUFFICIENT_DATA
    assert session.exec(select(Company)).all() == []


# --- upsert_run (linha run) ---------------------------------------------------


def test_upsert_run_maps_paused_run_to_awaiting_review(session: Session) -> None:
    # Estado devolvido ainda em RUNNING = pausa do HITL sync (F2.8) → awaiting_review (F2.10).
    run = upsert_run(session, _state(status=RunStatus.RUNNING))
    assert run.status is RunStatus.AWAITING_REVIEW


def test_upsert_run_copies_briefing_status_and_errors(session: Session) -> None:
    briefing = Briefing(
        empresa="Acme AI", status=BriefingStatus.FORA_DE_ESCOPO, resumo_executivo="..."
    )
    state = _state(status=RunStatus.OUT_OF_SCOPE, briefing=briefing)
    state.mode = ExecutionMode.DISCOVERY
    state.hitl = HITLMode.AUTO
    state.errors = ["orcamento de LLM atingido: max_calls", "extractor: persistência falhou"]
    run = upsert_run(session, state)

    assert run.status is RunStatus.OUT_OF_SCOPE
    assert run.briefing_status is BriefingStatus.FORA_DE_ESCOPO
    assert run.mode is ExecutionMode.DISCOVERY
    assert run.hitl is HITLMode.AUTO
    assert run.error is not None and "max_calls" in run.error


# --- wiring no job (run_graph_job) --------------------------------------------


class _StubRedis:
    # O runner fake não publica; o stub só evita tocar o broker real.
    def publish(self, channel: str, data: str) -> None:  # pragma: no cover
        pass


def test_run_graph_job_persists_outputs(engine) -> None:
    # O job grava as saídas a partir do estado final: runner fake devolve um estado povoado e
    # a sessão é injetada (SQLite); ao fim as linhas estão no banco e commitadas.
    state = _state(run_id="r-job")

    def runner(query, *, run_id, mode, hitl, checkpointer, on_event):  # noqa: ANN001, ARG001
        return state

    summary = run_graph_job(
        "Acme AI",
        run_id="r-job",
        redis_client=_StubRedis(),
        open_checkpointer=lambda: nullcontext(None),
        open_session=lambda: Session(engine),
        runner=runner,
    )

    assert summary["run_id"] == "r-job"
    # Lê numa sessão nova (a do job já commitou e fechou): as linhas persistiram.
    with Session(engine) as check:
        assert check.get(Run, "r-job") is not None
        assert check.exec(select(Company)).one().nome == "Acme AI"
        assert check.exec(select(ScoreRow)).one().run_id == "r-job"
        assert check.exec(select(RecommendationRow)).one().tech == "NVIDIA NIM"
