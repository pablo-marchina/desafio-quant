from __future__ import annotations

import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from radar.api.app import app
from radar.database.connection import get_db_path


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    db_path = Path(get_db_path())
    if db_path.exists():
        db_path.unlink()
    from radar.database import init_db

    init_db()
    yield
    if db_path.exists():
        db_path.unlink()



def _wait_for_run(client: TestClient, run_id: int, timeout_seconds: float = 30.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    payload: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not finish before timeout: {payload}")

def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint_points_to_docs_and_health() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["health"] == "/health"
    assert response.json()["docs"] == "/docs"


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
)
def test_local_frontend_cors_preflight(origin: str) -> None:
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_provider_preflight_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/providers/preflight")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["search_provider"] == "fixture"


def test_list_runs_empty() -> None:
    client = TestClient(app)
    response = client.get("/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_startups_empty() -> None:
    client = TestClient(app)
    response = client.get("/startups")
    assert response.status_code == 200
    assert response.json() == []


def test_list_sources_empty() -> None:
    client = TestClient(app)
    response = client.get("/sources")
    assert response.status_code == 200
    assert response.json() == []


def test_get_nonexistent_run() -> None:
    client = TestClient(app)
    response = client.get("/runs/999")
    assert response.status_code == 404


def test_get_nonexistent_startup() -> None:
    client = TestClient(app)
    response = client.get("/startups/nonexistent")
    assert response.status_code == 404


def test_run_analysis_with_empty_query_fails() -> None:
    client = TestClient(app)
    response = client.post("/runs", json={"query": ""})
    assert response.status_code == 400
    assert "query must not be empty" in response.text


def test_run_analysis_with_fixture_succeeds() -> None:
    client = TestClient(app)
    response = client.post("/runs", json={"query": "startup brasileira de IA"})
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "pending"

    completed = _wait_for_run(client, data["run_id"])
    assert completed["status"] == "completed"
    assert len(completed["steps"]) >= 1


def test_run_analysis_can_be_queried_afterwards() -> None:
    client = TestClient(app)
    post_resp = client.post("/runs", json={"query": "startup brasileira de IA"})
    run_id = post_resp.json()["run_id"]

    completed = _wait_for_run(client, run_id)
    assert completed["query"] == "startup brasileira de IA"
    assert completed["status"] == "completed"
    assert any(step["step_key"] == "search_planner" for step in completed["steps"])


def test_run_analysis_exposes_sources_and_claims_afterwards() -> None:
    client = TestClient(app)
    post_resp = client.post("/runs", json={"query": "startup brasileira de IA"})
    run_id = post_resp.json()["run_id"]
    _wait_for_run(client, run_id)

    sources_resp = client.get(f"/runs/{run_id}/sources")
    claims_resp = client.get(f"/runs/{run_id}/claims")
    all_sources_resp = client.get("/sources")

    assert sources_resp.status_code == 200
    assert claims_resp.status_code == 200
    assert all_sources_resp.status_code == 200
    assert len(sources_resp.json()) >= 1
    assert len(claims_resp.json()) >= 1
    assert any(s["claim_count"] >= 1 for s in sources_resp.json()), (
        f"No source has claims. Counts: {[s['claim_count'] for s in sources_resp.json()]}"
    )
