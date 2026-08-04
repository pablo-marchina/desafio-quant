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
    db_url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


def _startup_payload() -> dict:
    return {
        "name": "API Product Startup",
        "website": "https://api-product.example.com",
        "sector": "Enterprise AI",
        "description": "AI platform for production teams",
        "product_summary": "GPU inference optimization",
        "tags": ["product"],
        "evidence": [
            {
                "claim": "Operates GPU inference in production",
                "source_url": "https://api-product.example.com/platform",
                "source_type": "official_site",
                "quote_or_evidence": ("The platform operates GPU inference workloads in production."),
                "confidence": "high",
            },
            {
                "claim": "Uses NVIDIA GPUs for model serving",
                "source_url": "https://api-product.example.com/tech-stack",
                "source_type": "blog",
                "quote_or_evidence": "Stack includes NVIDIA A100 GPUs for model serving.",
                "confidence": "medium",
            },
            {
                "claim": "Supports enterprise model optimization",
                "source_url": "https://api-product.example.com/customers",
                "source_type": "official_site",
                "quote_or_evidence": "Enterprise customers use the platform for model optimization.",
                "confidence": "low",
            },
        ],
    }


@pytest.mark.integration
def test_product_api_persists_startup_run_brief_and_health(client: TestClient) -> None:
    created = client.post("/startups", json=_startup_payload())
    assert created.status_code == 201, created.text
    startup = created.json()
    assert startup["normalized_name"] == "api product startup"
    assert len(startup["evidence"]) == 3

    listed = client.get("/startups")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == startup["id"]

    fetched = client.get(f"/startups/{startup['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == startup["name"]

    run_response = client.post(
        f"/startups/{startup['id']}/analysis-runs",
        json={"use_rag": False},
    )
    assert run_response.status_code == 201, run_response.text
    run = run_response.json()
    assert run["status"] in {"completed", "degraded"}
    assert len(run["scores"]) == 4
    assert run["action_brief_id"]

    fetched_run = client.get(f"/analysis-runs/{run['id']}")
    assert fetched_run.status_code == 200
    fetched_run_data = fetched_run.json()
    assert fetched_run_data["run_id"] == run["id"]
    assert fetched_run_data["startup_id"] == startup["id"]
    assert fetched_run_data["action_brief"] is not None

    product_health = client.get("/health/product")
    assert product_health.status_code == 200
    assert product_health.json()["status"] == "ok"
    assert "api.db" in product_health.json()["database_url"]

    dependency_health = client.get("/health/dependencies")
    assert dependency_health.status_code == 200
    dependencies = {item["name"]: item for item in dependency_health.json()["dependencies"]}
    assert dependencies["product_database"]["available"] is True
    assert dependencies["qdrant"]["configured"] is False


@pytest.mark.integration
def test_product_api_rejects_duplicate_startup_and_missing_resources(
    client: TestClient,
) -> None:
    assert client.post("/startups", json=_startup_payload()).status_code == 201
    duplicate = client.post("/startups", json=_startup_payload())
    assert duplicate.status_code == 409

    assert client.get("/startups/missing").status_code == 404
    assert client.get("/analysis-runs/missing").status_code == 404
    assert client.get("/analysis-runs/missing/brief").status_code == 404
