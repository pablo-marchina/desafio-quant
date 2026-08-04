"""API HTTP do TAPI (FastAPI) — F5.2.

A camada que o front (F5.3+) consome e a fronteira do grafo multi-agente para o mundo. Os
runs longos (coleta + LLM) **não** cabem no request: `POST /runs` só **enfileira** (worker RQ,
F2.10) e devolve o `run_id`; `GET /runs/{id}` transmite o progresso ao vivo por **SSE** (canal
Redis pub/sub do worker); `POST /runs/{id}/resume` retoma o grafo após o HITL (F2.8/F5.10);
`GET /companies` serve a lista filtrável (F5.4/F5.11) e `GET /briefings/{id}` o relatório
executivo (F4.4) em JSON/Markdown/PDF (F4.6, base do export F5.8).

Recursos vivos (fila, Redis, sessão SQL, leitor de briefing) entram por **dependência**
(`apps/api/deps.py`), sobrescrevíveis em teste. A **autenticação** (gate interno, F5.9) entra
como `Depends(require_auth)` no `router` que carrega os endpoints de negócio — `/health` fica
fora do gate (probe de liveness, devolve `auth_required` p/ o front decidir se pede login).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from rq import Queue
from sqlmodel import Session

from apps.worker import enqueue_resume, enqueue_run
from packages.agents.briefing import render_markdown, render_pdf
from packages.agents.cohort_rag import rank_discovery
from packages.agents.discovery import parse_query, residual_query, summarize
from packages.agents.human_review import review_payload
from packages.agents.progress import ProgressEvent
from packages.config import get_settings
from packages.schemas import Briefing, GraphState
from packages.scoring.cohort_cluster import CohortClustering, cluster_cohort, load_cohort_points

from .companies import get_company_detail, list_companies, list_tech_facets
from .deps import (
    db_session,
    get_auth_token,
    get_briefing_loader,
    get_job_phase,
    get_langfuse_url,
    get_progress_source,
    get_queue,
    get_review_loader,
    get_trace_loader,
    require_auth,
)
from .schemas import (
    CompanyDetailOut,
    CompanyOut,
    DiscoverHitOut,
    DiscoverOut,
    EvidenceOut,
    RunAccepted,
    RunRequest,
    RunReviewOut,
    RunStatusOut,
    RunTraceOut,
    TechFacetsOut,
)
from .trace import build_run_trace

app = FastAPI(title="NVIDIA Startup AI Radar API", version="0.1.0")

# CORS (F5.2 ↔ F5.3): o front (origem :3000) chama a API (:8080) cross-origin; sem estes
# cabeçalhos o browser bloqueia a resposta mesmo com a API devolvendo 200. Origens vêm do
# settings (default = front no dev local). Auth via header Bearer, sem cookies → sem credenciais.
_cors_origins = [o.strip() for o in get_settings().cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints de negócio: todos atrás do gate interno (F5.9). `/health` fica no `app` (sem gate).
router = APIRouter(dependencies=[Depends(require_auth)])

QueueDep = Annotated[Queue, Depends(get_queue)]
SessionDep = Annotated[Session, Depends(db_session)]
_ProgressSource = Callable[[str], Iterable[ProgressEvent]]
ProgressSourceDep = Annotated[_ProgressSource, Depends(get_progress_source)]
JobPhaseDep = Annotated[Callable[[str], str], Depends(get_job_phase)]
BriefingLoaderDep = Annotated[Callable[[str], Briefing | None], Depends(get_briefing_loader)]
TraceLoaderDep = Annotated[Callable[[str], GraphState | None], Depends(get_trace_loader)]
ReviewLoaderDep = Annotated[
    Callable[[str], tuple[GraphState, bool] | None], Depends(get_review_loader)
]
LangfuseUrlDep = Annotated[str | None, Depends(get_langfuse_url)]
AuthTokenDep = Annotated[str, Depends(get_auth_token)]


@app.get("/health")
def health(token: AuthTokenDep) -> dict:
    """Liveness probe (aberto, sem gate F5.9) + diz se a API exige credencial (`auth_required`).

    O front (F5.3+) consulta isto no boot: `auth_required=true` (há `TAPI_API_TOKEN`) faz a UI
    pedir login antes de mostrar qualquer tela; `false` (dev/offline) libera direto.
    """
    return {"status": "ok", "auth_required": bool(token)}


# --- runs ---------------------------------------------------------------------


@router.post("/runs", status_code=202)
def create_run(req: RunRequest, queue: QueueDep) -> RunAccepted:
    """Enfileira um run do grafo (worker RQ, F2.10) e devolve o `run_id` p/ acompanhar via SSE."""
    run_id = enqueue_run(req.query, queue=queue, mode=req.mode, hitl=req.hitl)
    return RunAccepted(run_id=run_id, status="pending")


def _sse(events: Iterable[ProgressEvent]) -> Iterable[str]:
    """Serializa cada `ProgressEvent` como um frame SSE (`data: <json>\\n\\n`)."""
    for event in events:
        yield f"data: {event.model_dump_json()}\n\n"


@router.get("/runs/{run_id}")
def stream_run(run_id: str, source: ProgressSourceDep) -> StreamingResponse:
    """Acompanha um run ao vivo (SSE): assina o canal de progresso (F2.10) e repassa ao front."""
    return StreamingResponse(_sse(source(run_id)), media_type="text/event-stream")


@router.post("/runs/{run_id}/resume", status_code=202)
def resume_run(
    run_id: str,
    queue: QueueDep,
    decision: Annotated[dict | None, Body()] = None,
) -> RunAccepted:
    """Retoma um run pausado no HITL sync (F2.8) com a decisão do gerente (F5.10) via worker."""
    enqueue_resume(run_id, decision or {}, queue=queue)
    return RunAccepted(run_id=run_id, status="resuming")


@router.get("/runs/{run_id}/review")
def get_run_review(run_id: str, load: ReviewLoaderDep) -> RunReviewOut:
    """Payload da revisão HITL de um run (F5.10): classe/AIMI/recs p/ aprovar, editar ou rejeitar.

    Lê do estado persistido (checkpoint, F2.2) o `review_payload` (F2.8) e diz se o run está
    pausado no interrupt sync (`awaiting_review`). A tela de aprovação (F5.10) mostra o diagnóstico
    e, com a decisão do gerente, chama `POST /runs/{id}/resume`. `404` se o run não tem checkpoint
    (run inexistente); um run que já seguiu/concluiu responde `awaiting_review=false` (a UI sabe que
    não há mais o que aprovar). A decisão é registrada em `trace["human_review"]` (auditável, F2.8);
    *aplicá-la* para alterar o diagnóstico no briefing é gancho futuro de backend (F2.8/F4.4).
    """
    loaded = load(run_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="run não encontrado")
    state, awaiting = loaded
    return RunReviewOut(awaiting_review=awaiting, **review_payload(state))


@router.get("/runs/{run_id}/trace")
def get_run_trace(run_id: str, load: TraceLoaderDep, langfuse_url: LangfuseUrlDep) -> RunTraceOut:
    """Trace de um run (F5.7): os passos dos agentes (estado do grafo) + custo + link Langfuse.

    Reconstrói do estado persistido do run (checkpoint, F2.2) a espinha de nós (F2.1) com o que
    cada um produziu — offline-reproduzível, sem depender do Langfuse no ar; o `langfuse_url`
    (F0.8) entra como deep-trace opcional. `404` se o run não tem checkpoint.
    """
    state = load(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run não encontrado")
    return build_run_trace(state, langfuse_url=langfuse_url)


@router.get("/runs/{run_id}/status")
def get_run_status(run_id: str, phase_of: JobPhaseDep, load: ReviewLoaderDep) -> RunStatusOut:
    """Fase de um run p/ a UI reencontrar uma consulta longa ao voltar à tela (F5.3+).

    O worker (F2.10) mantém o run rodando mesmo se a tela fechar; este endpoint deixa a UI saber o
    que mostrar ao reabrir **sem pendurar no SSE** (o pub/sub não reentrega o progresso que já
    passou). Combina o status do job RQ — **autoritativo** p/ "ainda rodando" — com o checkpoint
    (F2.2): job na fila/executando → `running` (a UI reabre o stream); job caído → `failed`; job
    concluído + checkpoint pausado no interrupt (F2.8) → `awaiting_review`; concluído e terminal →
    `done` (+ o desfecho real); sem job nem checkpoint → `unknown` (run expirado/estranho → a UI
    descarta o run guardado). Nunca 404: a UI sempre recebe uma fase acionável.
    """
    phase = phase_of(run_id)
    if phase in {"running", "failed"}:
        return RunStatusOut(run_id=run_id, phase=phase)
    loaded = load(run_id)
    if loaded is None:
        return RunStatusOut(run_id=run_id, phase="unknown")
    state, awaiting = loaded
    if awaiting:
        return RunStatusOut(run_id=run_id, phase="awaiting_review")
    return RunStatusOut(run_id=run_id, phase="done", run_status=state.status.value)


# --- companies ----------------------------------------------------------------


@router.get("/companies")
def get_companies(
    session: SessionDep,
    setor: Annotated[str | None, Query()] = None,
    classificacao: Annotated[str | None, Query()] = None,
    min_aimi: Annotated[int | None, Query(ge=0, le=100)] = None,
    tech: Annotated[str | None, Query(description="Tech que a startup usa (F5.11).")] = None,
    nvidia_tech: Annotated[str | None, Query(description="Tech NVIDIA recomendada (F5.11).")] = (
        None
    ),
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[CompanyOut]:
    """Lista as startups (perfil + AIMI) filtráveis por setor/AIMI/classe (F5.4) e tech (F5.11)."""
    return list_companies(
        session,
        setor=setor,
        classificacao=classificacao,
        min_aimi=min_aimi,
        tech=tech,
        nvidia_tech=nvidia_tech,
        limit=limit,
    )


@router.get("/discover")
def discover_cohort(
    session: SessionDep,
    q: Annotated[str, Query(description="Pergunta em PT-BR sobre a coorte (F3.10/F5.12).")] = "",
) -> DiscoverOut:
    """Chat de descoberta da coorte (F3.10/F5.12): pergunta NL → filtros + ranking semântico.

    Dois estágios honestos: (1) `parse_query` traduz a pergunta nos **filtros estruturados** que
    `list_companies` já entende (tech NVIDIA recomendada · classe · piso de AIMI) — recorta *quem
    entra*; (2) `rank_discovery` decide *como ordenar*: se há **texto livre** (setor/domínio que o
    vocabulário não cobre, ex.: "fraude", "agro") re-ordena por **similaridade semântica**
    (`embeddings_use_nv` real ou hashing offline) e cita a evidência de cada match (§8); senão
    mantém a ordem por Inception Priority. "Suscetível à tech X" = o recommender prescreveu X.
    """
    query = parse_query(q)
    # Limite generoso: no modo semântico o ranking precisa enxergar a coorte **inteira** filtrada
    # (não só o top-N por prioridade) p/ não esconder um match relevante atrás do corte. Escala da
    # coorte é de dezenas — devolver tudo é barato e o chat ordena o que importa no topo.
    empresas = list_companies(
        session,
        setor=query.setor,
        classificacao=query.classificacao,
        min_aimi=query.min_aimi,
        tech=query.tech,
        nvidia_tech=query.nvidia_tech,
        limit=500,
    )
    by_id: dict[int, CompanyOut] = {e.id: e for e in empresas}
    ranking = rank_discovery(session, q, [e.id for e in empresas])

    resultados = [
        DiscoverHitOut(
            empresa=by_id[hit.company_id],
            similaridade=round(hit.similaridade, 3) if hit.similaridade is not None else None,
            citacao=(
                EvidenceOut(
                    url=hit.citacao.url,
                    snippet=hit.citacao.snippet,
                    source_title=hit.citacao.source_title,
                )
                if hit.citacao
                else None
            ),
        )
        for hit in ranking.hits
        if hit.company_id in by_id
    ]

    if ranking.modo == "semantico":
        livre = residual_query(q)
        tem_filtro = query.entendido != "toda a coorte, por prioridade de outreach"
        entendido = (
            f"{query.entendido}; busca: “{livre}”" if tem_filtro
            else f"busca semântica: “{livre}”"
        )
        plural = "startup" if len(resultados) == 1 else "startups"
        resumo = (
            f"Encontrei {len(resultados)} {plural} — {entendido} — "
            "ordenadas por relevância semântica à sua busca."
        )
    else:
        entendido = query.entendido
        resumo = summarize(query, len(resultados))

    return DiscoverOut(
        pergunta=q,
        entendido=entendido,
        resumo=resumo,
        modo=ranking.modo,
        resultados=resultados,
    )


@router.get("/companies/facets")
def get_company_facets(session: SessionDep) -> TechFacetsOut:
    """Vocabulário controlado dos filtros de tech da lista (F5.11): tags usadas + recomendadas.

    Varre a coorte inteira (independe dos filtros vigentes) e devolve as tags normalizadas de
    cada faceta — a startup **usa** (`tech`) / NVIDIA **recomenda** (`nvidia_tech`). A UI monta os
    controles a partir disto, então o `GET /companies?tech=&nvidia_tech=` só recebe tags que
    existem. Declarada **antes** de `/companies/{company_id}` p/ a rota fixa vencer a paramétrica.
    """
    tech, nvidia_tech = list_tech_facets(session)
    return TechFacetsOut(tech=tech, nvidia_tech=nvidia_tech)


@router.get("/cohort/clusters")
def get_cohort_clusters(
    session: SessionDep,
    k: Annotated[
        int | None, Query(ge=1, le=12, description="Nº de clusters (default auto).")
    ] = None,
) -> CohortClustering:
    """Radar de portfólio da coorte (F6.5–F6.7): clusters por perfil ordenados por prontidão ★.

    Agrupa a coorte (`company` + `Score` mais recente) por embedding de perfil (setor/stack) e
    ranqueia os clusters por prontidão de graduação (share de alvos ★ + Inception médio) — a leitura
    de portfólio do gerente (DSS nível 3). Determinístico/offline por default (hashing + numpy);
    cuML/nv-embedqa atrás de flag.
    """
    return cluster_cohort(load_cohort_points(session), k=k)


@router.get("/companies/{company_id}")
def get_company(company_id: int, session: SessionDep) -> CompanyDetailOut:
    """Detalhe de uma startup (F5.5): perfil + radar AIMI (4 pilares) com evidência por pilar.

    Alimenta a tela de detalhe (radar dos sub-scores + fontes citáveis); `404` se a empresa não
    existe. O breakdown vem do `Score` mais recente — empresa coletada mas não pontuada sai sem
    pilares (a UI degrada como a lista).
    """
    detail = get_company_detail(session, company_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="empresa não encontrada")
    return detail


# --- briefings ----------------------------------------------------------------


@router.get("/briefings/{run_id}")
def get_briefing(
    run_id: str,
    load: BriefingLoaderDep,
    format: Annotated[str, Query(pattern="^(json|md|pdf)$")] = "json",
) -> Any:
    """Relatório executivo de um run (F4.4) em JSON | Markdown | PDF (F4.6 — export F5.8).

    O briefing vem do estado persistido do run (checkpoint, F2.2); `404` se o run ainda não
    chegou ao briefing. `md`/`pdf` reusam os renderizadores deterministas do nó (F4.4/F4.6).
    """
    briefing = load(run_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="briefing não encontrado para o run")
    if format == "md":
        return PlainTextResponse(render_markdown(briefing), media_type="text/markdown")
    if format == "pdf":
        return Response(
            render_pdf(briefing),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="briefing-{run_id}.pdf"'},
        )
    return briefing


# Liga os endpoints de negócio (todos atrás do gate F5.9) ao app; `/health` segue aberto acima.
app.include_router(router)
