from fastapi.testclient import TestClient

from app.main import create_app


def test_classification_endpoint_returns_ai_maturity_assessment() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/classification/ai-maturity",
        json={
            "url": "https://medai.example",
            "title": "MedAI",
            "extracted_text": (
                "MedAI automates healthcare workflows with AI agents and LLM copilots. "
                "The platform uses proprietary data and production guardrails."
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["label"] in {"ai_native", "ai_enabled"}
    assert body["confidence"] > 0
    assert "ai_workflow_depth" in body["scores"]
    assert body["persisted"] is None
