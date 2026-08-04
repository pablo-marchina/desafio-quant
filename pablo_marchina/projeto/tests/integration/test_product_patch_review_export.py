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
    monkeypatch.setenv("PRODUCT_DATA_DIR", str(tmp_path / "product_data"))
    db_url = f"sqlite:///{(tmp_path / 'api_ext.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


@pytest.fixture
def startup(client: TestClient) -> dict:
    payload = {
        "name": "Patchable Startup",
        "website": "https://patchable.example.com",
        "sector": "Enterprise AI",
        "evidence": [
            {
                "claim": "Runs AI in production",
                "source_url": "https://patchable.example.com/tech",
                "source_type": "official_site",
                "quote_or_evidence": "We run production AI workloads.",
                "confidence": "high",
            }
        ],
    }
    resp = client.post("/startups", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.integration
def test_patch_startup_partial(client: TestClient, startup: dict) -> None:
    resp = client.patch(f"/startups/{startup['id']}", json={"sector": "AI Infrastructure"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sector"] == "AI Infrastructure"
    assert data["name"] == "Patchable Startup"


@pytest.mark.integration
def test_patch_startup_name_recalculates_normalized(client: TestClient, startup: dict) -> None:
    resp = client.patch(f"/startups/{startup['id']}", json={"name": "New Name"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["normalized_name"] == "new name"


@pytest.mark.integration
def test_patch_startup_does_not_delete_evidence(client: TestClient, startup: dict) -> None:
    resp = client.patch(f"/startups/{startup['id']}", json={"sector": "Changed"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data.get("evidence", [])) == 1


@pytest.mark.integration
def test_patch_startup_conflict(client: TestClient, startup: dict) -> None:
    other_payload = {
        "name": "Other Startup",
        "website": "https://other.example.com",
        "sector": "AI",
    }
    resp = client.post("/startups", json=other_payload)
    assert resp.status_code == 201

    resp = client.patch(f"/startups/{startup['id']}", json={"name": "Other Startup"})
    assert resp.status_code == 409


@pytest.mark.integration
def test_patch_startup_404(client: TestClient) -> None:
    resp = client.patch("/startups/nonexistent", json={"name": "X"})
    assert resp.status_code == 404


@pytest.mark.integration
def test_create_review(client: TestClient, startup: dict) -> None:
    run_resp = client.post(f"/startups/{startup['id']}/analysis-runs", json={"use_rag": False})
    assert run_resp.status_code == 201
    run = run_resp.json()

    review_resp = client.post(
        f"/analysis-runs/{run['id']}/review",
        json={"decision": "approve", "reviewer": "tester", "notes": "Good candidate"},
    )
    assert review_resp.status_code == 201
    data = review_resp.json()
    assert data["decision"] == "approve"
    assert data["reviewer"] == "tester"


@pytest.mark.integration
def test_create_review_404(client: TestClient) -> None:
    resp = client.post(
        "/analysis-runs/nonexistent/review",
        json={"decision": "approve", "reviewer": "tester"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_list_reviews(client: TestClient, startup: dict) -> None:
    run_resp = client.post(f"/startups/{startup['id']}/analysis-runs", json={"use_rag": False})
    run = run_resp.json()

    for dec in ["approve", "monitor"]:
        client.post(
            f"/analysis-runs/{run['id']}/review",
            json={"decision": dec, "reviewer": "tester"},
        )

    resp = client.get(f"/analysis-runs/{run['id']}/reviews")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.integration
def test_opportunities_endpoint(client: TestClient, startup: dict) -> None:
    client.post(f"/startups/{startup['id']}/analysis-runs", json={"use_rag": False})

    resp = client.get("/opportunities")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.integration
def test_create_export_json(client: TestClient, startup: dict) -> None:
    run_resp = client.post(f"/startups/{startup['id']}/analysis-runs", json={"use_rag": False})
    run = run_resp.json()

    export_resp = client.post(
        f"/analysis-runs/{run['id']}/exports",
        json={"export_type": "json"},
    )
    assert export_resp.status_code == 201
    data = export_resp.json()
    assert data["export_type"] == "json"
    assert data["status"] == "completed"
    assert data["content_hash"] != ""


@pytest.mark.integration
def test_create_export_markdown(client: TestClient, startup: dict) -> None:
    run_resp = client.post(f"/startups/{startup['id']}/analysis-runs", json={"use_rag": False})
    run = run_resp.json()

    export_resp = client.post(
        f"/analysis-runs/{run['id']}/exports",
        json={"export_type": "markdown"},
    )
    assert export_resp.status_code == 201
    data = export_resp.json()
    assert data["export_type"] == "markdown"
    assert data["status"] == "completed"


@pytest.mark.integration
def test_get_export(client: TestClient, startup: dict) -> None:
    run_resp = client.post(f"/startups/{startup['id']}/analysis-runs", json={"use_rag": False})
    run = run_resp.json()

    export_resp = client.post(
        f"/analysis-runs/{run['id']}/exports",
        json={"export_type": "json"},
    )
    export = export_resp.json()

    get_resp = client.get(f"/exports/{export['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == export["id"]


@pytest.mark.integration
def test_export_404(client: TestClient) -> None:
    resp = client.get("/exports/nonexistent")
    assert resp.status_code == 404
