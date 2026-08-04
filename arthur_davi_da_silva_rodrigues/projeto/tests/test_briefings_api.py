from uuid import UUID

from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import create_app


def test_generate_briefing_endpoint_returns_markdown() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/briefings",
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
    assert body["title"] == "MedAI - Relatório NVIDIA Startup AI Radar"
    assert "## Fit NVIDIA" in body["markdown"]
    assert body["source_urls"] == ["https://medai.example"]
    assert body["persisted"] is None


class FakeBriefing:
    id = UUID("11111111-1111-1111-1111-111111111111")
    startup_id = UUID("22222222-2222-2222-2222-222222222222")
    title = "MedAI persistida - Relatório NVIDIA Startup AI Radar"
    markdown = "# MedAI persistida\n\n## Fit NVIDIA\nTensorRT-LLM fit."
    source_summary = {"source_urls": ["https://persisted-medai.example"]}


def test_persisted_briefing_can_be_read_and_exported(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: object()

    def fake_get_briefing(db_session: object, briefing_id: UUID) -> FakeBriefing:
        return FakeBriefing()

    monkeypatch.setattr("app.api.routes.briefings.get_briefing", fake_get_briefing)
    client = TestClient(app)
    briefing_id = "11111111-1111-1111-1111-111111111111"

    read_response = client.get(f"/briefings/{briefing_id}")
    assert read_response.status_code == 200
    read_body = read_response.json()
    assert read_body["id"] == briefing_id
    assert read_body["startup_id"] == "22222222-2222-2222-2222-222222222222"
    assert "## Fit NVIDIA" in read_body["markdown"]

    export_response = client.post(f"/briefings/{briefing_id}/export")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("text/markdown")
    assert export_response.headers["content-disposition"].endswith(".md\"")
    assert "## Fit NVIDIA" in export_response.text


def test_missing_briefing_export_returns_404(monkeypatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: object()

    def fake_get_briefing(db_session: object, briefing_id: UUID) -> None:
        return None

    monkeypatch.setattr("app.api.routes.briefings.get_briefing", fake_get_briefing)
    client = TestClient(app)

    response = client.post("/briefings/00000000-0000-0000-0000-000000000000/export")

    assert response.status_code == 404


def test_email_report_returns_503_when_smtp_is_not_configured() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/briefings/email",
        json={
            "to_email": "vc@example.com",
            "subject": "Relatório NVIDIA Startup AI Radar",
            "markdown": "# Relatório\n\nConteúdo.",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "SMTP não configurado"
