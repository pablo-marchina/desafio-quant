from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts import run_product_acceptance


class _Response:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


class _Client:
    def __init__(self, _app: object) -> None:
        self.requests: list[tuple[str, str]] = []

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def request(self, method: str, path: str, json: dict[str, Any] | None = None) -> _Response:
        self.requests.append((method, path))
        if path == "/product/readiness":
            return _Response({"ready": True, "user_messages": []})
        if path == "/product/capabilities":
            return _Response([{"capability_id": str(i)} for i in range(30)])
        if path == "/startups":
            return _Response({"id": "startup-1"}, 201)
        if path.endswith("/analysis-runs"):
            return _Response({"id": "run-1", "status": "completed"}, 201)
        if path.endswith("/claims"):
            return _Response({"total": 1})
        if path.endswith("/evidence-coverage"):
            return _Response({"total_claims": 1})
        if path.endswith("/activation-recommendations/generate"):
            return _Response({"total": 1}, 201)
        if path.endswith("/dossier"):
            return _Response({"dossier": {"dossier_json": {"ok": True}}}, 201)
        if path.endswith("/quality-runs"):
            return _Response({"metrics": [{"name": "quality"}]}, 201)
        if path.endswith("/exports"):
            return _Response({"status": "completed"}, 201)
        return _Response({"error": "unexpected"}, 500)


def test_product_acceptance_report_passes_with_expected_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run_product_acceptance, "TestClient", _Client)
    monkeypatch.setattr(run_product_acceptance, "configure_product_database", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_product_acceptance, "reset_product_database_runtime", lambda: None)

    report = run_product_acceptance.run_acceptance(
        evidence_dir=tmp_path,
        database_url="postgresql://postgres:postgres@localhost:5432/startup_radar",
        qdrant_url="http://localhost:6333",
        qdrant_collection="nvidia_corpus",
    )

    assert report["status"] == "PASS"
    assert (tmp_path / "acceptance_report.json").is_file()
    assert [step["path"] for step in report["details"]["steps"]][0] == "/product/readiness"
