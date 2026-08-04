from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .llm_chat import answer_chat_message
from .schemas import AnalyzeStartupRequest, ChatRequest
from .service import create_analysis_session_store

app = FastAPI(title="NVIDIA Startup AI Radar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = create_analysis_session_store()


@app.get("/api/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.get("/api/startups")
def list_startups() -> list[dict]:
    return store.list_startups()


@app.post("/api/startups/analyze")
def analyze_startup(payload: AnalyzeStartupRequest) -> dict:
    try:
        return store.analyze_startup(payload.startup_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/startups/{startup_id}")
def get_startup(startup_id: str) -> dict:
    startup = store.get_startup(startup_id=startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup não encontrada.")
    return startup


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    startup = store.get_startup(startup_id=payload.startup_id, startup_name=payload.startup_name)
    try:
        return answer_chat_message(payload.message, startup)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
