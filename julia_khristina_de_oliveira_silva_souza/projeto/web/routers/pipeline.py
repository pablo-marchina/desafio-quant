import json
import os
import uuid
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["pipeline"])

_jobs: dict[str, dict] = {}


def _carregar_todos_setores() -> list[str]:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "pipeline", "config", "setores.json")
    with open(path, "r", encoding="utf-8") as f:
        return [s["id"] for s in json.load(f)]


class RunPipelineRequest(BaseModel):
    setor: str = ""


@router.post("/pipeline/run")
def run_pipeline(req: RunPipelineRequest):
    job_id = str(uuid.uuid4())
    setores_alvo = [req.setor] if req.setor else _carregar_todos_setores()
    _jobs[job_id] = {"status": "running", "setor": req.setor or "todos", "progresso": 0}

    try:
        from graph.graph import build_graph
        from graph.state import AgentState

        total = len(setores_alvo)
        for i, setor_id in enumerate(setores_alvo):
            state: AgentState = {
                "setor_alvo": setor_id,
                "consulta_usuario": None,
                "queries_geradas": [],
                "startups_coletadas": [],
                "erros": [],
                "startups_classificadas": [],
                "startups_validadas": [],
                "recomendacoes_rag": [],
                "recomendacoes_finais": [],
                "briefings": [],
                "etapa_atual": "",
                "iteracao": 0
            }

            graph = build_graph()
            resultado = graph.invoke(state)
            _jobs[job_id]["progresso"] = round((i + 1) / total * 100)

        _jobs[job_id] = {
            "status": "completed",
            "setor": req.setor or "todos",
            "startups": len(resultado.get("startups_coletadas", [])),
            "briefings": len(resultado.get("briefings", [])),
            "erros": len(resultado.get("erros", []))
        }
    except Exception as e:
        _jobs[job_id] = {"status": "failed", "erro": str(e)}

    return {"job_id": job_id}


@router.get("/pipeline/status/{job_id}")
def pipeline_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        return {"erro": "Job não encontrado"}, 404
    return job
