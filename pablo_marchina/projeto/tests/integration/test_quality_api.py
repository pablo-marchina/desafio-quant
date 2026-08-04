from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.session import configure_product_database, reset_product_database_runtime


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    monkeypatch.setenv("QDRANT_URL", "")
    db_url = f"sqlite:///{(tmp_path / 'quality_api.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


def _create_startup_and_run(client: TestClient) -> dict:
    startup = client.post(
        "/startups",
        json={
            "name": "Quality API Startup",
            "website": "https://quality-api.example.com",
            "sector": "AI Infrastructure",
            "description": "Quality test startup",
            "tags": ["quality"],
        },
    ).json()
    run = client.post(
        f"/startups/{startup['id']}/analysis-runs",
        json={"use_rag": False},
    ).json()
    return run


@pytest.mark.integration
def test_create_quality_run(client: TestClient) -> None:
    run = _create_startup_and_run(client)
    response = client.post(f"/analysis-runs/{run['id']}/quality-runs")
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["analysis_run_id"] == run["id"]
    assert data["status"] in ("completed", "degraded")
    assert len(data["metrics"]) > 0
    assert data["evaluator_version"] == "1.0"


@pytest.mark.integration
def test_list_quality_runs(client: TestClient) -> None:
    run = _create_startup_and_run(client)
    client.post(f"/analysis-runs/{run['id']}/quality-runs")
    response = client.get(f"/analysis-runs/{run['id']}/quality-runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["analysis_run_id"] == run["id"]


@pytest.mark.integration
def test_get_latest_quality_run(client: TestClient) -> None:
    run = _create_startup_and_run(client)
    client.post(f"/analysis-runs/{run['id']}/quality-runs")
    response = client.get(f"/analysis-runs/{run['id']}/quality-runs/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["analysis_run_id"] == run["id"]
    assert data["status"] in ("completed", "degraded")


@pytest.mark.integration
def test_get_quality_summary(client: TestClient) -> None:
    run = _create_startup_and_run(client)
    client.post(f"/analysis-runs/{run['id']}/quality-runs")
    response = client.get(f"/analysis-runs/{run['id']}/quality-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] in ("pass", "warn", "degraded", "no_quality_run")
    assert data["total_metrics"] > 0
    assert data["quality_run_id"] is not None


@pytest.mark.integration
def test_create_quality_run_missing_analysis_run(client: TestClient) -> None:
    response = client.post("/analysis-runs/nonexistent/quality-runs")
    assert response.status_code == 404


@pytest.mark.integration
def test_get_latest_quality_run_not_found(client: TestClient) -> None:
    run = _create_startup_and_run(client)
    response = client.get(f"/analysis-runs/{run['id']}/quality-runs/latest")
    assert response.status_code == 404


@pytest.mark.integration
def test_get_quality_summary_no_quality_run(client: TestClient) -> None:
    run = _create_startup_and_run(client)
    response = client.get(f"/analysis-runs/{run['id']}/quality-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "no_quality_run"
    assert data["quality_run_id"] is None


@pytest.mark.integration
def test_re_evaluate_quality_replaces_previous_run(client: TestClient) -> None:
    run = _create_startup_and_run(client)
    r1 = client.post(f"/analysis-runs/{run['id']}/quality-runs").json()
    r2 = client.post(f"/analysis-runs/{run['id']}/quality-runs").json()
    assert r1["id"] != r2["id"]
    listing = client.get(f"/analysis-runs/{run['id']}/quality-runs").json()
    assert len(listing) == 1
    assert listing[0]["id"] == r2["id"]
