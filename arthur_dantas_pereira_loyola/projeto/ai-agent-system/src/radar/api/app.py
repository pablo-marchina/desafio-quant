from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

_src = str(Path(__file__).resolve().parent.parent.parent)
if _src not in sys.path:
    sys.path.insert(0, _src)

from alembic.config import Config as AlembicConfig  # noqa: E402
from alembic import command as alembic_command  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from radar.database import (  # noqa: E402
    create_contact_discovery_run,
    ensure_contact_discovery_steps_registered,
    get_all_runs,
    get_all_source_documents,
    get_all_startups,
    get_contact_discovery_run,
    get_contact_discovery_steps,
    get_contacts_by_startup,
    get_run_by_id,
    get_run_evidence_claims,
    get_run_recommendations,
    get_run_source_documents,
    get_run_steps,
    get_run_validation,
    get_runs_by_startup,
    get_startup_by_id,
    init_db,
    save_contacts,
    save_evidence_claim,
    save_recommendation,
    save_run,
    save_run_briefing,
    save_source_document,
    save_startup,
    save_validation,
    update_contact_discovery_status,
    update_contact_discovery_step,
    update_run_startup,
    update_run_status,
)
from radar.database.connection import get_db_path  # noqa: E402
from radar.graph.builder import build_graph  # noqa: E402
from radar.graph.progress import PipelineTracker, set_tracker  # noqa: E402
from radar.scraping.provider_preflight import inspect_provider_setup  # noqa: E402


_DB_DIR = Path(__file__).resolve().parent.parent / "database"
_ALEMBIC_INI = _DB_DIR / "alembic.ini"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    if _ALEMBIC_INI.is_file():
        cfg = AlembicConfig(str(_ALEMBIC_INI))
        cfg.set_main_option(
            "script_location",
            str(_DB_DIR / "alembic"),
        )
        alembic_command.upgrade(cfg, "head")
    init_db()

    _prewarm_vector_store()
    _prewarm_playwright_pool()
    yield


def _prewarm_playwright_pool() -> None:
    try:
        from radar.scraping.playwright_pool import get_pool

        pool = get_pool()
        import logging
        logging.getLogger("radar").info("PlaywrightPool instantiated (size=%d). Warmup deferred to first use.", pool.size())
    except Exception:
        pass


def _prewarm_vector_store() -> None:
    try:
        from radar.rag.retriever import ensure_seeded

        def _warm():
            import logging
            logging.getLogger("radar").info("Pre-warming vector store (sentence-transformers)...")
            ensure_seeded()
            logging.getLogger("radar").info("Vector store pre-warmed successfully.")

        t = threading.Thread(target=_warm, daemon=True)
        t.start()
    except Exception:
        pass


app = FastAPI(title="NVIDIA Startup AI Radar", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    query: str
    startup_name: str | None = None


class BatchStartupItem(BaseModel):
    startup_name: str
    query: str


class BatchRequest(BaseModel):
    startups: list[BatchStartupItem]
    concurrency: int = 4


def _persist_run_result(run_id: int, result: dict[str, Any]) -> None:  # noqa: C901
    classification_data = result.get("classification")
    startup_data = (
        result.get("extracted_startups", [None])[0]
        if result.get("extracted_startups")
        else None
    )

    if startup_data:
        startup_dict: dict[str, Any] = {
            **startup_data.model_dump(),
            "classification_label": classification_data.label
            if classification_data
            else None,
            "classification_confidence": classification_data.confidence
            if classification_data
            else None,
            "classification_rationale": classification_data.rationale
            if classification_data
            else None,
        }
        startup_id = save_startup(startup_dict)
        update_run_startup(run_id, startup_id)

        for src in result.get("sources", []):
            save_source_document(run_id, src.model_dump())

        for claim in result.get("claims", []):
            save_evidence_claim(run_id, claim.model_dump())

        validation = result.get("validation")
        if validation:
            save_validation(run_id, validation.model_dump())

        for rec in result.get("recommendations", []):
            save_recommendation(run_id, rec.model_dump())

        briefing = result.get("briefing")
        if briefing:
            save_run_briefing(run_id, json.dumps(jsonable_encoder(briefing.model_dump())))

        update_run_status(run_id, "completed")
    else:
        update_run_status(run_id, "failed")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "NVIDIA Startup AI Radar",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict[str, object]:
    import sqlite3

    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        conn.close()
        size = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
        return {
            "status": "ok",
            "path": db_path,
            "tables": tables,
            "table_count": len(tables),
            "size_bytes": size,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/providers/preflight")
def provider_preflight() -> dict[str, object]:
    return asdict(inspect_provider_setup())


@app.post("/runs")
def run_analysis(payload: RunRequest) -> dict[str, Any]:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    run_id = save_run(query)
    update_run_status(run_id, "pending")

    tracker = PipelineTracker(run_id)
    tracker.ensure_steps_registered()

    threading.Thread(
        target=_run_pipeline_background,
        args=(run_id, query, tracker, payload.startup_name),
        daemon=True,
    ).start()

    return jsonable_encoder({"run_id": run_id, "status": "pending"})


def _run_pipeline_background(run_id: int, query: str, tracker: PipelineTracker, startup_name: str | None = None) -> None:
    update_run_status(run_id, "running")
    set_tracker(tracker)
    try:
        graph = build_graph()
        initial_state: dict[str, Any] = {"query": query, "collection_attempts": 0}
        if startup_name:
            initial_state["startup_name"] = startup_name
        result: dict[str, Any] = graph.invoke(initial_state)
        _persist_run_result(run_id, result)
    except Exception as exc:
        import logging
        import traceback
        logging.getLogger("radar").error("Pipeline run %d failed: %s\n%s", run_id, exc, traceback.format_exc())
        update_run_status(run_id, "failed")
    finally:
        set_tracker(None)


@app.get("/runs")
def list_runs() -> list[dict[str, Any]]:
    return get_all_runs()


@app.get("/sources")
def list_sources() -> list[dict[str, Any]]:
    return get_all_source_documents()


@app.get("/runs/{run_id}/sources")
def get_run_sources(run_id: int) -> list[dict[str, Any]]:
    if not get_run_by_id(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return get_run_source_documents(run_id)


@app.get("/runs/{run_id}/claims")
def get_run_claims(run_id: int) -> list[dict[str, Any]]:
    if not get_run_by_id(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return get_run_evidence_claims(run_id)


@app.get("/runs/{run_id}")
def get_run(run_id: int) -> dict[str, Any]:
    run = get_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run["recommendations"] = get_run_recommendations(run_id)
    run["steps"] = get_run_steps(run_id)
    run["validation"] = get_run_validation(run_id)
    if run.get("briefing"):
        import json
        try:
            run["briefing"] = json.loads(run["briefing"])
        except Exception:
            pass
    return run


@app.get("/runs/{run_id}/stream")
def stream_pipeline(run_id: int):
    if not get_run_by_id(run_id):
        raise HTTPException(status_code=404, detail="Run not found")

    def event_stream():
        last_data: Any = None
        while True:
            steps = get_run_steps(run_id)
            if steps != last_data:
                last_data = steps
                yield f"data: {json.dumps(steps)}\n\n"
            statuses = {s["status"] for s in steps}
            if statuses == {"completed"} or ("error" in statuses and not statuses - {"completed", "error"}):
                yield "event: done\ndata: {}\n\n"
                break
            time.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/batches")
def run_batch(payload: BatchRequest) -> dict[str, Any]:
    items = [m.model_dump() for m in payload.startups]
    if not items:
        raise HTTPException(status_code=400, detail="startups list must not be empty")

    from radar.database.repository import create_batch

    batch_id = create_batch(items)

    threading.Thread(
        target=_run_batch_background,
        args=(batch_id, items, payload.concurrency),
        daemon=True,
    ).start()

    return jsonable_encoder({"batch_id": batch_id, "status": "running", "total": len(items)})


@app.get("/batches/{batch_id}")
def get_batch_status(batch_id: int) -> dict[str, Any]:
    from radar.database.repository import get_batch

    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return jsonable_encoder(batch)


def _run_batch_background(batch_id: int, items: list[dict[str, str]], concurrency: int) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from radar.database.repository import complete_batch, get_batch, update_batch_item
    from radar.graph.builder import build_graph

    def _run_single(item: dict[str, str]) -> tuple[str, str | None]:
        try:
            startup_name = item["startup_name"]
            query = item["query"]

            run_id = save_run(query)
            update_run_status(run_id, "running")

            graph = build_graph()
            initial_state: dict[str, Any] = {"query": query, "collection_attempts": 0}
            if startup_name:
                initial_state["startup_name"] = startup_name
            result = graph.invoke(initial_state)
            _persist_run_result(run_id, result)
            return "completed", str(run_id)
        except Exception as exc:
            import logging
            logging.getLogger("radar").error("Batch item %s failed: %s", item["startup_name"], exc)
            return "failed", str(exc)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(_run_single, item): item for item in items}
        for future in as_completed(future_map):
            item = future_map[future]
            try:
                status, detail = future.result()
            except Exception as exc:
                status, detail = "failed", str(exc)

            batch = get_batch(batch_id)
            if batch and batch.get("items"):
                for bi in batch["items"]:
                    if bi["startup_name"] == item["startup_name"] and bi["query"] == item["query"]:
                        run_id = int(detail) if status == "completed" and detail else None
                        error_msg = detail if status == "failed" else None
                        update_batch_item(bi["id"], run_id=run_id, status=status, error_message=error_msg)
                        break

    complete_batch(batch_id)


@app.get("/startups")
def list_startups() -> list[dict[str, Any]]:
    return get_all_startups()


@app.get("/startups/{startup_id}")
def get_startup(startup_id: str) -> dict[str, Any]:
    startup = get_startup_by_id(startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    return startup


@app.get("/startups/{startup_id}/runs")
def list_startup_runs(startup_id: str) -> list[dict[str, Any]]:
    if not get_startup_by_id(startup_id):
        raise HTTPException(status_code=404, detail="Startup not found")
    return get_runs_by_startup(startup_id)


@app.post("/startups/{startup_id}/contacts")
def discover_startup_contacts(startup_id: str) -> dict[str, Any]:
    startup = get_startup_by_id(startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")

    existing = get_contacts_by_startup(startup_id)
    if existing:
        return jsonable_encoder({"startup_id": startup_id, "cached": True, "contacts": existing})

    discovery_id = create_contact_discovery_run(startup_id)
    ensure_contact_discovery_steps_registered(discovery_id)
    update_contact_discovery_status(discovery_id, "running")

    threading.Thread(
        target=_run_contact_discovery_background,
        args=(discovery_id, startup_id, startup["name"]),
        daemon=True,
    ).start()

    return jsonable_encoder({"startup_id": startup_id, "discovery_id": discovery_id, "status": "running"})


def _run_contact_discovery_background(discovery_id: int, startup_id: str, startup_name: str) -> None:
    from radar.agents.contact_discovery import discover_contacts
    from radar.agents.contact_tracker import ContactDiscoveryTracker, set_contact_tracker

    tracker = ContactDiscoveryTracker(discovery_id)
    set_contact_tracker(tracker)
    try:
        result = discover_contacts(startup_id=startup_id, startup_name=startup_name)
        save_contacts(startup_id, result.model_dump())
        update_contact_discovery_status(discovery_id, "completed")
    except Exception as exc:
        import logging
        logging.getLogger("radar").error("Contact discovery %d failed: %s", discovery_id, exc)
        update_contact_discovery_status(discovery_id, "failed")
        update_contact_discovery_step(discovery_id, "saving_result", "error", str(exc))
    finally:
        set_contact_tracker(None)


@app.get("/startups/{startup_id}/contacts/stream")
def stream_contact_discovery(startup_id: str):
    run_data = get_contact_discovery_run(startup_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="No contact discovery running")
    discovery_id = run_data["id"]

    def event_stream():
        last_data: Any = None
        while True:
            steps = get_contact_discovery_steps(discovery_id)
            if steps != last_data:
                last_data = steps
                yield f"data: {json.dumps(steps)}\n\n"
            statuses = {s["status"] for s in steps}
            if statuses == {"completed"} or ("error" in statuses and not statuses - {"completed", "error"}):
                yield "event: done\ndata: {}\n\n"
                break
            time.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/startups/{startup_id}/contacts")
def get_startup_contacts(startup_id: str) -> dict[str, Any]:
    if not get_startup_by_id(startup_id):
        raise HTTPException(status_code=404, detail="Startup not found")
    contacts = get_contacts_by_startup(startup_id)
    if not contacts:
        return {"startup_id": startup_id, "emails": [], "phones": [], "linkedin_urls": [], "addresses": [], "raw_text_snippets": []}
    return contacts


