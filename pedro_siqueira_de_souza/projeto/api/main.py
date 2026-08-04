"""Aplicação FastAPI do NVISION.

Semana 1: apenas o esqueleto — `/health` para validar que o backend sobe e
um endpoint de demonstração que executa o grafo LangGraph de 2 nós. Os
endpoints reais do ux.md (§7.2) entram nas semanas seguintes:

    POST /api/pipeline/run        WS /api/pipeline/{id}/stream
    GET  /api/startups            GET /api/analytics  ...

Rode com:  uv run uvicorn api.main:app --reload
Docs em:   http://localhost:8000/docs
"""
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from agents.graph import graph
from core.config import settings
from database import repo

app = FastAPI(
    title="NVISION — NVIDIA Startup AI Radar",
    version="0.1.0",
    description="Plataforma multi-agente de inteligência estratégica para o NVIDIA Inception.",
)

# CORS liberado para o frontend Vite em desenvolvimento (porta 5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["infra"])
def health() -> dict:
    """Liveness check. Confirma que o backend está no ar e qual LLM está ativo."""
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "llm_provider": settings.llm_provider,
    }


class PlanRequest(BaseModel):
    query: str


@app.post("/api/demo/plan", tags=["demo"])
def demo_plan(req: PlanRequest) -> dict:
    """Executa o grafo e devolve só o PLANO de busca (search_planner).

    Endpoint leve para inspecionar o que o Search Planner produziu sem precisar
    do payload completo. Para o resultado completo, use `/api/pipeline/run`.
    """
    final_state = graph.invoke({"query": req.query})
    return {
        "search_terms": final_state.get("search_terms", []),
        "sources": final_state.get("sources", []),
        "trace": [str(m) for m in final_state.get("messages", [])],
    }


class PipelineRequest(BaseModel):
    query: str


@app.post("/api/pipeline/run", tags=["pipeline"])
def pipeline_run(req: PipelineRequest) -> dict:
    """Executa o pipeline multi-agente COMPLETO e devolve o resultado.

    Roda os 9 nós (search_planner -> ... -> briefing) e expõe as saídas que
    interessam à interface: as startups classificadas, as recomendações de
    stack NVIDIA e os briefings executivos (markdown), além do trace do grafo.

    Atenção: é uma chamada SÍNCRONA e pode demorar (scraping + LLM + RAG por
    startup). O endpoint com streaming (ux.md §7.2) entra com a interface.
    """
    final_state = graph.invoke({"query": req.query})
    # Persiste o resultado para as páginas Qualificadas/Analytics (resiliente:
    # uma falha de banco não derruba a resposta do pipeline).
    salvas = repo.persist_pipeline_result(final_state)
    return {
        "query": req.query,
        "search_terms": final_state.get("search_terms", []),
        "sources": final_state.get("sources", []),
        "classified_startups": final_state.get("classified_startups", []),
        "recommendations": final_state.get("recommendations", []),
        "briefings": final_state.get("briefings", []),
        "persisted": salvas,
        "trace": [str(m) for m in final_state.get("messages", [])],
    }


# Ordem dos estágios no caminho feliz do grafo (agents/graph.py). O frontend usa
# isso para desenhar o stepper já com todos os passos ANTES de qualquer evento, e
# o backend para traduzir o nome técnico do nó num rótulo legível. Fonte única da
# sequência exibida — o ciclo do evidence_validator (volta pro scraper) apenas
# re-emite estágios já existentes, sem quebrar a lista.
PIPELINE_STAGES: list[tuple[str, str]] = [
    ("search_planner", "Planejando busca"),
    ("scraper", "Coletando startups"),
    ("relevance", "Filtrando por relevância"),
    ("enricher", "Enriquecendo páginas"),
    ("extractor", "Estruturando dados"),
    ("classifier", "Classificando maturidade IA"),
    ("evidence_validator", "Validando evidências"),
    ("rag", "Consultando base NVIDIA"),
    ("recommendation", "Recomendando stack NVIDIA"),
    ("briefing", "Gerando briefings"),
]
_STAGE_LABELS = dict(PIPELINE_STAGES)


def _sse(event: dict) -> str:
    """Formata um dict como um frame SSE (`data: <json>\\n\\n`)."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _ultima_mensagem(update: dict) -> str | None:
    """Texto legível da última `message` que um nó emitiu (para o stepper).

    `add_messages` pode entregar tuplas ("ai", texto) ou objetos de mensagem
    (com `.content`) — tratamos os dois sem assumir um formato só."""
    msgs = update.get("messages") if isinstance(update, dict) else None
    if not msgs:
        return None
    ultima = msgs[-1]
    if isinstance(ultima, (tuple, list)) and len(ultima) == 2:
        return str(ultima[1])
    return getattr(ultima, "content", None) or str(ultima)


@app.post("/api/pipeline/stream", tags=["pipeline"])
def pipeline_stream(req: PipelineRequest) -> StreamingResponse:
    """Versão STREAMING do pipeline: emite progresso por nó via SSE.

    Diferença para `/run`: em vez de bloquear e responder só no fim, usa
    `graph.stream(...)` e manda um evento a cada nó concluído — a interface
    mostra em qual estágio o grafo está e o que cada agente produziu. No fim,
    persiste e envia o resultado completo (mesmo shape do `/run`).

    Modos de stream combinados: "updates" dá o nó que acabou de rodar (para o
    progresso); "values" dá o estado completo a cada passo — guardamos o último
    para montar o payload final sem reconstruir o estado na mão.
    """

    def gen():
        # Esqueleto: a sequência de estágios, para o front desenhar tudo de cara.
        yield _sse({
            "type": "start",
            "stages": [{"node": n, "label": rotulo} for n, rotulo in PIPELINE_STAGES],
        })
        final_state: dict = {}
        try:
            for mode, chunk in graph.stream(
                {"query": req.query}, stream_mode=["updates", "values"]
            ):
                if mode == "values":
                    final_state = chunk  # último snapshot = estado final
                    continue
                # mode == "updates": {nome_do_nó: atualização_que_ele_retornou}
                for node, update in chunk.items():
                    yield _sse({
                        "type": "node",
                        "node": node,
                        "label": _STAGE_LABELS.get(node, node),
                        "message": _ultima_mensagem(update),
                    })
            # Persiste (resiliente) e fecha com o resultado completo.
            salvas = repo.persist_pipeline_result(final_state)
            yield _sse({
                "type": "done",
                "result": {
                    "query": req.query,
                    "search_terms": final_state.get("search_terms", []),
                    "sources": final_state.get("sources", []),
                    "classified_startups": final_state.get("classified_startups", []),
                    "recommendations": final_state.get("recommendations", []),
                    "briefings": final_state.get("briefings", []),
                    "persisted": salvas,
                    "trace": [str(m) for m in final_state.get("messages", [])],
                },
            })
        except Exception as e:  # nunca derruba a conexão sem avisar o cliente
            logger.exception("pipeline_stream falhou")
            yield _sse({"type": "error", "error": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        # Evita buffering intermediário (proxies/nginx) que atrasaria os eventos.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/startups", tags=["startups"])
def list_startups(limit: int = 200) -> dict:
    """Lista as startups acumuladas no banco (página Qualificadas).

    Diferente do pipeline (que roda os agentes), aqui só LÊ o que já foi
    qualificado e persistido — rápido e sem custo de LLM.
    """
    return {"startups": repo.list_startups(limit)}


@app.get("/api/startups/{name}", tags=["startups"])
def get_startup(name: str) -> dict:
    """Detalhe de uma startup (dropdown da página Qualificadas): sobre a empresa,
    produtos NVIDIA compatíveis e o briefing executivo. 404 se não existir."""
    detalhe = repo.get_startup(name)
    if detalhe is None:
        raise HTTPException(status_code=404, detail=f"startup '{name}' não encontrada")
    return detalhe


@app.get("/api/analytics", tags=["startups"])
def analytics() -> dict:
    """Visão agregada do ecossistema (página Analytics): total, distribuição
    por maturidade de IA e por setor."""
    return repo.analytics()
