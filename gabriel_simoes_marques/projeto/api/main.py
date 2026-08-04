import asyncio
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph.pipeline import pipeline
from graph.state import PipelineState
from models.briefing import BriefingReport
from models.debate import DebateResult
from models.score import StartupScore
from models.ranking import RankingReport
from agents.debate import run_debate
from agents.scorer import score_startup
from agents.ranker import rank_startups
from agents.batch import _run_one
from agents.synergy import analyze_synergy, SynergyResult
from config.llm import DEFAULT_MODEL, OPENROUTER_MODELS

app = FastAPI(title="NVIDIA Startup AI Radar", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    startup_name: str
    urls: list[str] = []
    model: str = DEFAULT_MODEL


@app.get("/models")
async def list_models():
    return {"models": list(OPENROUTER_MODELS.keys()), "default": DEFAULT_MODEL}


@app.post("/analyze", response_model=BriefingReport)
async def analyze_startup(req: AnalyzeRequest):
    initial_state: PipelineState = {
        "startup_name": req.startup_name,
        "urls": req.urls,
        "model": req.model,
        "startup": None,
        "recommendations": [],
        "briefing": None,
        "error": None,
    }

    result = await pipeline.ainvoke(initial_state)

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    if result.get("briefing") is None:
        raise HTTPException(status_code=500, detail="Pipeline falhou sem gerar briefing")

    return result["briefing"]


class ScoreRequest(BaseModel):
    report: BriefingReport
    model: str = DEFAULT_MODEL


@app.post("/score", response_model=StartupScore)
async def score_startup_endpoint(req: ScoreRequest):
    return await score_startup(req.report, model=req.model)


class RankRequest(BaseModel):
    scores: list[StartupScore]
    model: str = DEFAULT_MODEL


@app.post("/rank", response_model=RankingReport)
async def rank_startups_endpoint(req: RankRequest):
    return await rank_startups(req.scores, model=req.model)


class CompareRequest(BaseModel):
    report_a: BriefingReport
    report_b: BriefingReport
    model_a: str = DEFAULT_MODEL
    model_b: str = DEFAULT_MODEL
    judge_model: str = DEFAULT_MODEL


@app.post("/compare", response_model=DebateResult)
async def compare_startups(req: CompareRequest):
    result = await run_debate(
        req.report_a, req.report_b,
        model_a=req.model_a,
        model_b=req.model_b,
        judge_model=req.judge_model,
    )
    return result


class BatchRequest(BaseModel):
    startups: list[str]
    model: str = DEFAULT_MODEL
    concurrency: int = 2


@app.post("/batch")
async def batch_analyze(req: BatchRequest):
    """SSE stream: cada startup emite um evento quando completa."""
    sem = asyncio.Semaphore(req.concurrency)

    async def stream():
        async def run_and_emit(name: str):
            result = await _run_one(name, [], req.model, sem)
            payload = {
                "startup_name": name,
                "success": result.success,
                "error": result.error,
                "report": result.report.model_dump() if result.report else None,
                "score": result.score.model_dump() if result.score else None,
            }
            return f"data: {json.dumps(payload)}\n\n"

        tasks = [run_and_emit(name) for name in req.startups]
        for coro in asyncio.as_completed(tasks):
            yield await coro
        yield "data: {\"done\": true}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


class SynergyRequest(BaseModel):
    target: BriefingReport
    peer: BriefingReport
    model: str = DEFAULT_MODEL


@app.post("/synergy", response_model=SynergyResult)
async def synergy_endpoint(req: SynergyRequest):
    return await analyze_synergy(req.target, req.peer, model=req.model)


_TECH_EXCLUDE = {
    "NVIDIA", "NVIDIA hardware", "NVIDIA platform", "NVIDIA software",
    "NVIDIA Inception", "NVIDIA Inception Startup Showcase", "NVIDIA Inception program",
    "NVIDIA GPUs", "NVIDIA NVLink", "NVIDIA NVSwitch", "NVIDIA RTX", "NVIDIA A100",
    "NVIDIA Blackwell GPUs", "docs.nvidia.com/nemo/guardrails",
}

_TECH_QUERY = """
    MATCH (n:Entity)
    WHERE n.name =~ '(?i).*nvidia.*'
       OR n.name IN ['CUDA','CUDA Tile C++','CUDA Toolkit 13.3','cuDF','cudf.pandas',
                     'TensorRT','TensorRT-LLM','RAPIDS','RAPIDS FIL',
                     'NeMo Guardrails','Nemotron']
    RETURN DISTINCT n.name AS name ORDER BY name
"""


@app.get("/techs")
async def list_techs():
    from neo4j import AsyncGraphDatabase
    from config.settings import settings
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    async with driver.session(database=settings.neo4j_database) as session:
        result = await session.run(_TECH_QUERY)
        rows = await result.values()
    await driver.close()
    techs = sorted({r[0] for r in rows if r[0] not in _TECH_EXCLUDE})
    return {"techs": techs}


@app.get("/health")
async def health():
    return {"status": "ok"}
