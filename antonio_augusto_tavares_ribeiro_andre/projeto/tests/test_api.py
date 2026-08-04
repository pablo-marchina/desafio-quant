"""Testes da API HTTP (F5.2) — endpoints do grafo, lista e briefing.

Tudo offline via `app.dependency_overrides`: a fila RQ, a fonte de progresso (SSE), a sessão
SQL (SQLite em memória) e o leitor de briefing entram como stubs — sem broker, Postgres nem
worker. Exercita:
- `POST /runs` / `POST /runs/{id}/resume`: enfileiram o job certo e devolvem o `run_id` (202);
- `GET /runs/{id}`: transmite o progresso como SSE (`text/event-stream`, frames `data:`);
- `GET /companies`: projeta perfil + AIMI e aplica os filtros (setor/AIMI/classe + tech F5.11),
  ordenando por `inception_priority`;
- `GET /briefings/{id}`: serve o relatório em JSON/Markdown/PDF e dá 404 sem briefing.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from apps.api.deps import (
    db_session,
    get_auth_token,
    get_briefing_loader,
    get_job_phase,
    get_langfuse_url,
    get_progress_source,
    get_queue,
    get_review_loader,
    get_trace_loader,
)
from apps.api.main import app
from apps.api.trace import build_run_trace
from apps.worker import resume_graph_job, run_graph_job
from packages.agents.briefing import build_briefing
from packages.agents.progress import END_NODE, ProgressEvent
from packages.db.models import Company, Evidence, Run, Score
from packages.db.models import Recommendation as RecommendationRow
from packages.schemas import (
    AIMIScore,
    Classification,
    GraphState,
    PillarScore,
    RawDocument,
    Recommendation,
    RetrievedChunk,
    ROIEstimate,
    RunStatus,
    StartupProfile,
)
from packages.schemas import Evidence as SchemaEvidence
from packages.schemas.enums import AIMIPillar


class _RecordingQueue:
    """Stub da fila RQ que registra o `enqueue` (sem broker), como em `test_worker`."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def enqueue(self, func, *args, **kwargs) -> None:  # noqa: ANN001 — assina como o RQ
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})


def _aimi(total_pillar: int, classe: Classification) -> AIMIScore:
    def _p(pilar: AIMIPillar) -> PillarScore:
        return PillarScore(pilar=pilar, score=total_pillar, justificativa="sinal")

    return AIMIScore(
        data_moat=_p(AIMIPillar.DATA_MOAT),
        workflow_depth=_p(AIMIPillar.WORKFLOW_DEPTH),
        technical_optimization=_p(AIMIPillar.TECHNICAL_OPTIMIZATION),
        distribution_moat=_p(AIMIPillar.DISTRIBUTION_MOAT),
        classificacao=classe,
    )


def _seed(session: Session) -> None:
    """Duas empresas pontuadas (saúde/fintech) + uma sem score, com techs e recomendações."""
    session.add(Run(id="r1", query="Acme Health"))
    session.add(Run(id="r2", query="Bolt Pay"))

    acme = Company(
        nome="Acme Health",
        setor="saude",
        tecnologias=[{"nome": "OpenAI"}, {"nome": "LangChain"}],
        run_id="r1",
    )
    bolt = Company(nome="Bolt Pay", setor="fintech", tecnologias=[{"nome": "PyTorch"}], run_id="r2")
    cold = Company(nome="Cold Start", setor="saude", tecnologias=[])
    session.add_all([acme, bolt, cold])
    session.flush()

    acme_score = Score(
        company_id=acme.id,
        run_id="r1",
        classificacao=Classification.AI_NATIVE,
        total=80,
        inception_priority=90,
        data_moat=20,
        workflow_depth=20,
        technical_optimization=20,
        distribution_moat=20,
        just_data_moat="dataset proprietário de prontuários anotados",
    )
    session.add(acme_score)
    session.flush()
    # Evidência de um pilar (entity_type='score', field=<pilar>) — a fonte citável do radar (F5.5).
    session.add(
        Evidence(
            url="https://acme.health/dados",
            snippet="base proprietária com 2M de prontuários rotulados",
            fetched_at=datetime.now(UTC),
            source_title="Acme Health — Tecnologia",
            entity_type="score",
            entity_id=acme_score.id,
            field="data_moat",
        )
    )
    session.add(
        Score(
            company_id=bolt.id,
            run_id="r2",
            classificacao=Classification.AI_ENABLED,
            total=40,
            inception_priority=30,
            data_moat=10,
            workflow_depth=10,
            technical_optimization=10,
            distribution_moat=10,
        )
    )
    acme_rec = RecommendationRow(
        company_id=acme.id,
        run_id="r1",
        tech="NVIDIA NIM",
        justificativa_tecnica="serving otimizado",
        justificativa_negocio="reduz custo",
        prioridade="alta",
        complexidade="media",
        proxima_acao="testar NIM",
        pilar_origem=AIMIPillar.TECHNICAL_OPTIMIZATION,
        # ROI opcional (F6): número degrada gracioso quando ausente; aqui presente.
        roi={
            "throughput_speedup": 3.0,
            "cost_delta_pct": -60.0,
            "baseline": "API externa",
            "optimized": "NIM local",
            "is_live_run": False,
        },
    )
    session.add(acme_rec)
    session.flush()
    # Evidência dos dois lados da recomendação (F4.7): field='gap' (startup) / 'nvidia' (KB).
    session.add(
        Evidence(
            url="https://acme.health/inferencia",
            snippet="usa API externa paga para toda a inferência",
            fetched_at=datetime.now(UTC),
            entity_type="recommendation",
            entity_id=acme_rec.id,
            field="gap",
        )
    )
    session.add(
        Evidence(
            url="https://build.nvidia.com/nim",
            snippet="NIM serve modelos otimizados na própria GPU",
            fetched_at=datetime.now(UTC),
            entity_type="recommendation",
            entity_id=acme_rec.id,
            field="nvidia",
        )
    )
    session.commit()


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        _seed(s)
        yield s


@pytest.fixture
def queue() -> _RecordingQueue:
    return _RecordingQueue()


@pytest.fixture
def client(session: Session, queue: _RecordingQueue):
    app.dependency_overrides[db_session] = lambda: session
    app.dependency_overrides[get_queue] = lambda: queue
    # Gate F5.9 aberto por padrão (token vazio) — determinístico, independe do `.env` do dev.
    # Os testes de auth abaixo sobrescrevem `get_auth_token` p/ o modo fechado.
    app.dependency_overrides[get_auth_token] = lambda: ""
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- runs ---------------------------------------------------------------------


def test_create_run_enqueues_and_returns_run_id(client: TestClient, queue: _RecordingQueue) -> None:
    resp = client.post("/runs", json={"query": "Acme AI", "mode": "discovery", "hitl": "auto"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] and body["status"] == "pending"

    assert len(queue.calls) == 1
    call = queue.calls[0]
    assert call["func"] is run_graph_job
    assert call["args"] == ("Acme AI",)
    assert call["kwargs"]["job_id"] == body["run_id"]
    assert call["kwargs"]["mode"] == "discovery"
    assert call["kwargs"]["hitl"] == "auto"


def test_create_run_rejects_empty_query(client: TestClient) -> None:
    assert client.post("/runs", json={"query": ""}).status_code == 422


def test_resume_run_enqueues_resume_job(client: TestClient, queue: _RecordingQueue) -> None:
    resp = client.post("/runs/r1/resume", json={"approved": True, "nota": "ok"})
    assert resp.status_code == 202
    assert resp.json() == {"run_id": "r1", "status": "resuming"}

    call = queue.calls[0]
    assert call["func"] is resume_graph_job
    assert call["args"] == ("r1", {"approved": True, "nota": "ok"})
    assert call["kwargs"]["job_id"] == "r1-resume"  # dash, não `:` (RQ valida o job_id)


def test_stream_run_emits_sse_frames(client: TestClient) -> None:
    events = [
        ProgressEvent(run_id="r1", node="scraper", status="running", pct=20),
        ProgressEvent(run_id="r1", node=END_NODE, status="completed", pct=100),
    ]
    app.dependency_overrides[get_progress_source] = lambda: lambda run_id: events

    resp = client.get("/runs/r1")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "data: " in resp.text
    assert "scraper" in resp.text
    assert END_NODE in resp.text


# --- companies ----------------------------------------------------------------


def test_companies_projects_profile_and_aimi(client: TestClient) -> None:
    rows = client.get("/companies").json()
    by_name = {r["nome"]: r for r in rows}

    acme = by_name["Acme Health"]
    assert acme["classificacao"] == "AI-native"
    assert acme["aimi_total"] == 80
    assert acme["inception_priority"] == 90
    assert sorted(acme["tecnologias"]) == ["LangChain", "OpenAI"]
    # Tag normalizada (vocabulário controlado F5.11): "NVIDIA NIM" -> "NIM".
    assert acme["nvidia_techs"] == ["NIM"]
    # Empresa sem score aparece sem diagnóstico (não alucina AIMI).
    assert by_name["Cold Start"]["aimi_total"] is None


def test_companies_ordered_by_inception_priority(client: TestClient) -> None:
    names = [r["nome"] for r in client.get("/companies").json()]
    # priority desc (90, 30) e a sem score por último.
    assert names == ["Acme Health", "Bolt Pay", "Cold Start"]


def test_companies_filter_by_setor(client: TestClient) -> None:
    names = [r["nome"] for r in client.get("/companies?setor=fintech").json()]
    assert names == ["Bolt Pay"]


def test_companies_filter_by_min_aimi_and_classe(client: TestClient) -> None:
    assert [r["nome"] for r in client.get("/companies?min_aimi=50").json()] == ["Acme Health"]
    high = client.get("/companies?classificacao=AI-native").json()
    assert [r["nome"] for r in high] == ["Acme Health"]


def test_companies_filter_by_tech_facets(client: TestClient) -> None:
    # Filtro pelo vocabulário controlado (F5.11): a tag normalizada casa por igualdade,
    # qualquer que seja a grafia enviada (apelido, prefixo "NVIDIA", caixa).
    assert [r["nome"] for r in client.get("/companies?tech=langchain").json()] == ["Acme Health"]
    assert [r["nome"] for r in client.get("/companies?nvidia_tech=nim").json()] == ["Acme Health"]
    assert [r["nome"] for r in client.get("/companies?nvidia_tech=NVIDIA NIM").json()] == [
        "Acme Health"
    ]
    # Substring não casa mais (determinístico): "Lang" não é a tag "LangChain".
    assert client.get("/companies?tech=Lang").json() == []


def test_companies_facets_lists_controlled_vocabulary(client: TestClient) -> None:
    facets = client.get("/companies/facets").json()
    # Tags usadas pela coorte (Acme: OpenAI/LangChain; Bolt: PyTorch), normalizadas e ordenadas.
    assert facets["tech"] == ["LangChain", "OpenAI", "PyTorch"]
    # Tag NVIDIA recomendada, colapsada do rótulo de exibição "NVIDIA NIM".
    assert facets["nvidia_tech"] == ["NIM"]


def test_companies_limit(client: TestClient) -> None:
    assert len(client.get("/companies?limit=1").json()) == 1


# --- discover / chat de descoberta (F3.10/F5.12) ------------------------------


def test_discover_modo_filtro_por_tech_recomendada(client: TestClient) -> None:
    # "NIM" é filtro puro (sem texto livre) → ordem por Inception Priority, sem similaridade.
    data = client.get("/discover?q=quais sao candidatas a NIM?").json()
    assert data["modo"] == "filtro"
    nomes = [h["empresa"]["nome"] for h in data["resultados"]]
    assert nomes == ["Acme Health"]  # só a que tem NIM recomendado
    assert data["resultados"][0]["similaridade"] is None


def test_discover_modo_semantico_ranqueia_e_cita(client: TestClient) -> None:
    # "saude" é texto livre (fora do vocabulário de filtro) → modo semântico. Asserção robusta ao
    # embedder (hashing no CI ou nv-embed real): a empresa de saúde fica acima da de fintech por
    # relevância, e a que tem evidência carrega a citação que sustenta o match (§8).
    data = client.get("/discover?q=startups de saude").json()
    assert data["modo"] == "semantico"
    nomes = [h["empresa"]["nome"] for h in data["resultados"]]
    assert nomes.index("Acme Health") < nomes.index("Bolt Pay")  # saúde > fintech (semântico)

    acme = next(h for h in data["resultados"] if h["empresa"]["nome"] == "Acme Health")
    assert acme["similaridade"] is not None
    assert acme["citacao"] is not None and acme["citacao"]["url"].startswith("https://")
    # Radar de portfolio (F6.5-F6.7): agrupa a coorte seedada e devolve clusters ranqueados.
    data = client.get("/cohort/clusters").json()
    assert data["n_companies"] == 3  # Acme, Bolt, Cold Start
    assert data["method"] == "numpy"  # default offline
    assert data["clusters"]  # ao menos um cluster
    membros = [m["nome"] for c in data["clusters"] for m in c["members"]]
    assert set(membros) == {"Acme Health", "Bolt Pay", "Cold Start"}
    # Acme (AI-native, pilares altos, tech-opt alto=20) nao e alvo de graduacao (P3 nao e baixo).
    acme = next(m for c in data["clusters"] for m in c["members"] if m["nome"] == "Acme Health")
    assert acme["graduation_ready"] is False
    assert acme["x"] is not None and acme["y"] is not None


def test_cohort_clusters_k_param(client: TestClient) -> None:
    data = client.get("/cohort/clusters?k=2").json()
    assert len(data["clusters"]) == 2  # k respeitado (n=3 >= 2)
    assert sum(c["size"] for c in data["clusters"]) == 3  # ninguem perdido


# --- company detail (F5.5) ----------------------------------------------------


def _company_id(client: TestClient, nome: str) -> int:
    return next(r["id"] for r in client.get("/companies").json() if r["nome"] == nome)


def test_company_detail_returns_pillars_and_evidence(client: TestClient) -> None:
    cid = _company_id(client, "Acme Health")
    detail = client.get(f"/companies/{cid}").json()

    assert detail["nome"] == "Acme Health"
    assert detail["classificacao"] == "AI-native"
    assert detail["aimi_total"] == 80
    assert detail["nvidia_techs"] == ["NIM"]

    # Os 4 pilares na ordem canônica, com faixa derivada do sub-score (RUBRICA §1).
    pilares = {p["pilar"]: p for p in detail["pilares"]}
    assert [p["pilar"] for p in detail["pilares"]] == [
        "data_moat",
        "workflow_depth",
        "technical_optimization",
        "distribution_moat",
    ]
    data_moat = pilares["data_moat"]
    assert data_moat["score"] == 20
    assert data_moat["band"] == "forte"  # 20 > 18 → forte
    assert data_moat["justificativa"].startswith("dataset proprietário")
    # A evidência do pilar vem com link à fonte (F5.5).
    assert data_moat["evidencias"][0]["url"] == "https://acme.health/dados"
    # Pilar sem evidência persistida degrada gracioso (lista vazia, não erro).
    assert pilares["workflow_depth"]["evidencias"] == []


def test_company_detail_returns_recommendation_cards(client: TestClient) -> None:
    # Cartão da recomendação (§5.5/F5.6): justificativas, pilar de origem, ROI e os dois lados.
    cid = _company_id(client, "Acme Health")
    recs = client.get(f"/companies/{cid}").json()["recomendacoes"]
    assert len(recs) == 1

    nim = recs[0]
    assert nim["tech"] == "NVIDIA NIM"
    assert nim["prioridade"] == "alta"
    assert nim["complexidade"] == "media"
    assert nim["proxima_acao"] == "testar NIM"
    assert nim["pilar_origem"] == "technical_optimization"
    # ROI (F6) presente: ganho de throughput + economia de custo.
    assert nim["roi"]["throughput_speedup"] == 3.0
    assert nim["roi"]["cost_delta_pct"] == -60.0
    assert nim["roi"]["optimized"] == "NIM local"
    # Evidência dos dois lados, cada uma com link à fonte (invariante F4.5).
    assert nim["evidencia_gap"][0]["url"] == "https://acme.health/inferencia"
    assert nim["evidencia_nvidia"][0]["url"] == "https://build.nvidia.com/nim"


def test_company_detail_orders_recommendations_and_roi_optional(
    client: TestClient, session: Session
) -> None:
    # Insere fora de ordem e sem ROI: o detalhe reordena alta→baixa e degrada sem o número.
    bolt_id = _company_id(client, "Bolt Pay")
    for tech, prioridade in (("Tech Baixa", "baixa"), ("Tech Alta", "alta")):
        session.add(
            RecommendationRow(
                company_id=bolt_id,
                run_id="r2",
                tech=tech,
                justificativa_tecnica="jt",
                justificativa_negocio="jn",
                prioridade=prioridade,
                complexidade="baixa",
                proxima_acao="acao",
            )
        )
    session.commit()

    recs = client.get(f"/companies/{bolt_id}").json()["recomendacoes"]
    assert [r["tech"] for r in recs] == ["Tech Alta", "Tech Baixa"]
    assert recs[0]["roi"] is None  # sem ROI → cartão degrada gracioso (F5.6)


def test_company_detail_without_score_has_no_pillars(client: TestClient) -> None:
    cid = _company_id(client, "Cold Start")
    detail = client.get(f"/companies/{cid}").json()
    assert detail["aimi_total"] is None
    assert detail["pilares"] == []


def test_company_detail_404_when_absent(client: TestClient) -> None:
    assert client.get("/companies/999999").status_code == 404


# --- briefings ----------------------------------------------------------------


def _briefing():
    # pilares <=6 dispensam evidência (RUBRICA §0); só precisamos de um AIMI válido p/ o relatório.
    return build_briefing(
        _aimi(5, Classification.AI_NATIVE), None, [], empresa="Acme Health", run_id="r1"
    )


def test_briefing_json_md_and_pdf(client: TestClient) -> None:
    app.dependency_overrides[get_briefing_loader] = lambda: lambda run_id: _briefing()

    js = client.get("/briefings/r1")
    assert js.status_code == 200
    assert js.json()["empresa"] == "Acme Health"

    md = client.get("/briefings/r1?format=md")
    assert md.headers["content-type"].startswith("text/markdown")
    assert "Briefing executivo" in md.text

    pdf = client.get("/briefings/r1?format=pdf")
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_briefing_404_when_absent(client: TestClient) -> None:
    app.dependency_overrides[get_briefing_loader] = lambda: lambda run_id: None
    assert client.get("/briefings/missing").status_code == 404


def test_briefing_rejects_bad_format(client: TestClient) -> None:
    app.dependency_overrides[get_briefing_loader] = lambda: lambda run_id: _briefing()
    assert client.get("/briefings/r1?format=xml").status_code == 422


# --- run trace (F5.7) ---------------------------------------------------------


def _scored_state(status: RunStatus, **extra) -> GraphState:
    """Run que chegou ao classifier (perfil + AIMI) num dado status — base dos casos de trace."""
    return GraphState(
        run_id="r1",
        query="Acme Health",
        status=status,
        search_terms=["acme"],
        sources=["https://acme.health"],
        raw_docs=[
            RawDocument(url="https://acme.health", content="x", fetched_at=datetime.now(UTC))
        ],
        profile=StartupProfile(nome="Acme Health"),
        # score ≤ 6 dispensa evidência (RUBRICA §0); total = 5×4 = 20.
        aimi=_aimi(5, Classification.AI_NATIVE),
        **extra,
    )


def _completed_state(run_id: str = "r1") -> GraphState:
    """Run que percorreu a espinha inteira (briefing pronto) — com rollup de custo carimbado."""
    now = datetime.now(UTC)
    state = _scored_state(
        RunStatus.COMPLETED,
        retrieved=[RetrievedChunk(text="NIM serve modelos na GPU")],
        recommendations=[
            Recommendation(
                tech="NVIDIA NIM",
                justificativa_tecnica="serving otimizado",
                justificativa_negocio="reduz custo",
                prioridade="alta",
                complexidade="media",
                proxima_acao="testar NIM",
                evidencia_gap=[
                    SchemaEvidence(
                        url="https://acme.health/infra", snippet="API externa", fetched_at=now
                    )
                ],
                evidencia_nvidia=[
                    SchemaEvidence(
                        url="https://build.nvidia.com/nim", snippet="NIM na GPU", fetched_at=now
                    )
                ],
                roi=ROIEstimate(throughput_speedup=3.0),
            )
        ],
        benchmark=ROIEstimate(throughput_speedup=3.0),
        briefing=_briefing(),
        trace={
            "usage": {
                "input_tokens": 1200,
                "output_tokens": 300,
                "total_tokens": 1500,
                "calls": 4,
                "cost_usd": 0.012,
            }
        },
    )
    return state.model_copy(update={"run_id": run_id})


def test_build_run_trace_marks_done_steps_with_summary() -> None:
    by_node = {s.node: s for s in build_run_trace(_completed_state()).steps}

    assert by_node["search_planner"].summary == "1 termos · 1 fontes"
    assert by_node["scraper"].summary == "1 documentos coletados"
    assert by_node["extractor"].summary == "perfil: Acme Health"
    assert by_node["classifier"].summary.startswith("AI-native · AIMI")
    assert by_node["evidence_validator"].summary == "evidências validadas"
    assert by_node["nvidia_rag"].summary == "1 trechos da KB NVIDIA"
    assert by_node["gpu_benchmark"].summary == "ROI estimado"
    assert by_node["human_review"].summary == "aprovado"  # completed → revisão concluída
    assert by_node["briefing"].status == "done"
    assert all(s.status == "done" for s in by_node.values())


def test_build_run_trace_terminal_branch_skips_unreached() -> None:
    # Ramo terminal de baixa confiança (F2.12): evidence_validator salta ao briefing, pulando o
    # miolo (rag/recommender/benchmark/human_review) — que sai como `skipped`, não `pending`.
    state = _scored_state(RunStatus.INSUFFICIENT_DATA, briefing=_briefing())
    by_node = {s.node: s.status for s in build_run_trace(state).steps}

    assert by_node["classifier"] == "done"
    assert by_node["evidence_validator"] == "done"
    assert by_node["briefing"] == "done"
    for node in ("nvidia_rag", "recommender", "gpu_benchmark", "human_review"):
        assert by_node[node] == "skipped"


def test_build_run_trace_pending_when_not_terminal() -> None:
    # Run pausado p/ revisão (HITL sync, F2.8): o que ainda não rodou fica `pending`, não `skipped`.
    steps = build_run_trace(_scored_state(RunStatus.AWAITING_REVIEW)).steps
    by_node = {s.node: s.status for s in steps}
    assert by_node["classifier"] == "done"
    assert by_node["human_review"] == "pending"
    assert by_node["briefing"] == "pending"


def test_build_run_trace_passes_langfuse_url_and_budget() -> None:
    # Sem `usage` no trace (run offline sem LLM) o rollup é omitido; a nota de orçamento (F2.11)
    # e o link Langfuse (F0.8) passam adiante.
    state = _scored_state(RunStatus.COMPLETED, trace={"budget": {"limited": True, "reason": "x"}})
    trace = build_run_trace(state, langfuse_url="http://langfuse.local")
    assert trace.langfuse_url == "http://langfuse.local"
    assert trace.budget_limited is True
    assert trace.usage is None


def test_run_trace_endpoint_returns_steps(client: TestClient) -> None:
    app.dependency_overrides[get_trace_loader] = lambda: lambda run_id: _completed_state(run_id)
    body = client.get("/runs/r1/trace").json()

    assert body["run_id"] == "r1"
    assert body["status"] == "completed"
    classifier = next(s for s in body["steps"] if s["node"] == "classifier")
    assert classifier["status"] == "done"
    assert body["usage"]["calls"] == 4


def test_run_trace_endpoint_404_when_absent(client: TestClient) -> None:
    app.dependency_overrides[get_trace_loader] = lambda: lambda run_id: None
    assert client.get("/runs/missing/trace").status_code == 404


def test_run_trace_endpoint_includes_langfuse_url(client: TestClient) -> None:
    app.dependency_overrides[get_trace_loader] = lambda: (
        lambda run_id: _scored_state(RunStatus.COMPLETED)
    )
    app.dependency_overrides[get_langfuse_url] = lambda: "http://langfuse.local"
    assert client.get("/runs/r1/trace").json()["langfuse_url"] == "http://langfuse.local"


# --- run review / HITL (F5.10) ------------------------------------------------


def test_run_review_endpoint_projects_payload_when_awaiting(client: TestClient) -> None:
    # Run pausado no interrupt sync (F2.8): o loader devolve (estado, awaiting=True). O endpoint
    # projeta o review_payload — classe/AIMI/recs — que a tela de aprovação (F5.10) mostra.
    app.dependency_overrides[get_review_loader] = lambda: (
        lambda run_id: (_completed_state(run_id), True)
    )
    body = client.get("/runs/r1/review").json()

    assert body["run_id"] == "r1"
    assert body["awaiting_review"] is True
    assert body["empresa"] == "Acme Health"
    assert body["classificacao"] == "AI-native"
    assert body["aimi_total"] == 20  # _aimi(5, ...) → 5×4 pilares
    assert body["recomendacoes"] == ["NVIDIA NIM"]


def test_run_review_endpoint_not_awaiting_when_resumed(client: TestClient) -> None:
    # Run que já seguiu/concluiu (checkpoint sem `next`): existe, mas não há mais o que aprovar —
    # 200 com awaiting_review=False (a UI distingue de 404/run inexistente).
    app.dependency_overrides[get_review_loader] = lambda: (
        lambda run_id: (_completed_state(run_id), False)
    )
    assert client.get("/runs/r1/review").json()["awaiting_review"] is False


def test_run_review_endpoint_404_when_absent(client: TestClient) -> None:
    app.dependency_overrides[get_review_loader] = lambda: lambda run_id: None
    assert client.get("/runs/missing/review").status_code == 404


# --- run status / reconexao da consulta (F5.3+) -------------------------------


def _phase(value: str):
    """Override do get_job_phase: fixa a fase do job RQ sem broker."""
    return lambda: lambda run_id: value


def test_run_status_running_when_job_in_flight(client: TestClient) -> None:
    # Job na fila/executando: a UI reabre o SSE ao vivo (nao consulta o checkpoint).
    app.dependency_overrides[get_job_phase] = _phase("running")
    body = client.get("/runs/r1/status").json()
    assert body == {"run_id": "r1", "phase": "running", "run_status": None}


def test_run_status_failed_when_job_failed(client: TestClient) -> None:
    app.dependency_overrides[get_job_phase] = _phase("failed")
    assert client.get("/runs/r1/status").json()["phase"] == "failed"


def test_run_status_awaiting_review_when_job_done_and_paused(client: TestClient) -> None:
    # Job concluido + checkpoint pausado no interrupt (next nao-vazio) = aguarda revisao (F2.8).
    app.dependency_overrides[get_job_phase] = _phase("finished")
    app.dependency_overrides[get_review_loader] = lambda: (
        lambda run_id: (_completed_state(run_id), True)
    )
    assert client.get("/runs/r1/status").json()["phase"] == "awaiting_review"


def test_run_status_done_carries_outcome(client: TestClient) -> None:
    # Job concluido + checkpoint sem `next` = terminou; carrega o desfecho real p/ a UI hidratar.
    app.dependency_overrides[get_job_phase] = _phase("finished")
    app.dependency_overrides[get_review_loader] = lambda: (
        lambda run_id: (_completed_state(run_id), False)
    )
    body = client.get("/runs/r1/status").json()
    assert body["phase"] == "done"
    assert body["run_status"] == "completed"


def test_run_status_unknown_when_no_job_nor_checkpoint(client: TestClient) -> None:
    # Job expirou do RQ e nao ha checkpoint: run guardado pela UI ficou orfao -> ela o descarta.
    app.dependency_overrides[get_job_phase] = _phase("absent")
    app.dependency_overrides[get_review_loader] = lambda: lambda run_id: None
    assert client.get("/runs/r1/status").json()["phase"] == "unknown"


def test_run_status_behind_gate(client: TestClient) -> None:
    # Endpoint de negocio: exige credencial quando o gate (F5.9) esta fechado.
    _gate_closed()
    assert client.get("/runs/r1/status").status_code == 401


# --- auth / gate interno (F5.9) -----------------------------------------------

TOKEN = "s3cret-interno"


def _gate_closed() -> None:
    """Fecha o gate (token configurado) — os endpoints de negócio passam a exigir credencial."""
    app.dependency_overrides[get_auth_token] = lambda: TOKEN


def test_health_open_and_reports_auth_not_required(client: TestClient) -> None:
    # /health fica fora do gate; em modo aberto (token vazio) sinaliza auth_required=False.
    body = client.get("/health").json()
    assert body == {"status": "ok", "auth_required": False}


def test_health_reports_auth_required_when_token_set(client: TestClient) -> None:
    # /health continua aberto (sem credencial) mas avisa o front que a API exige login.
    _gate_closed()
    body = client.get("/health").json()
    assert body == {"status": "ok", "auth_required": True}


def test_gate_open_allows_business_endpoints(client: TestClient) -> None:
    # Sem token configurado (default do fixture) os endpoints respondem sem credencial.
    assert client.get("/companies").status_code == 200


def test_gate_rejects_business_endpoints_without_credential(client: TestClient) -> None:
    _gate_closed()
    assert client.get("/companies").status_code == 401
    assert client.post("/runs", json={"query": "Acme AI"}).status_code == 401
    assert client.get("/companies/1").status_code == 401


def test_gate_accepts_bearer_token(client: TestClient) -> None:
    _gate_closed()
    resp = client.get("/companies", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200


def test_gate_accepts_x_api_key_header(client: TestClient) -> None:
    _gate_closed()
    assert client.get("/companies", headers={"X-API-Key": TOKEN}).status_code == 200


def test_gate_accepts_query_token_for_sse_and_pdf(client: TestClient) -> None:
    # SSE (EventSource) e o PDF (<a>) não mandam header, então o token vai na query (F5.2/F5.8).
    _gate_closed()
    assert client.get(f"/companies?token={TOKEN}").status_code == 200


def test_gate_rejects_wrong_credential(client: TestClient) -> None:
    _gate_closed()
    assert client.get("/companies", headers={"Authorization": "Bearer errado"}).status_code == 401
