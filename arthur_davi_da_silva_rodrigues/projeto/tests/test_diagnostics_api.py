from fastapi.testclient import TestClient

from app.main import create_app


def test_diagnostics_endpoint_returns_gap_report() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/diagnostics/gaps",
        json={
            "url": "https://medai.example",
            "title": "MedAI",
            "extracted_text": (
                "MedAI automates healthcare workflows with AI agents and LLM copilots. "
                "The platform uses OpenAI APIs and has latency pressure."
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    gap_types = {gap["gap_type"] for gap in body["gaps"]}
    assert "external_api_dependency" in gap_types
    assert "inference_latency_or_cost" in gap_types
    assert body["summary"].startswith("Foram detectados")
