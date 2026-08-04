from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import full_proof_pass_attempt


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _doctor_payload(status: str, route: str) -> dict[str, Any]:
    return {
        "status": status,
        "effective_service_route": route,
        "recommended_route": "recommended",
        "human_summary": "summary",
        "exact_commands": ["python scripts/local_proof_doctor.py"],
        "can_retry_without_code_changes": status == "BLOCKED_BY_ENVIRONMENT",
    }


def test_attempt_does_not_start_docker_when_doctor_is_blocked(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], timeout_seconds: int) -> dict[str, Any]:
        commands.append(command)
        if any("local_proof_doctor.py" in part for part in command):
            _write_json(
                tmp_path / "local_proof_doctor_report.json",
                _doctor_payload("BLOCKED_BY_ENVIRONMENT", "blocked_no_service_route"),
            )
        if any("prove_final_product.py" in part for part in command):
            _write_json(tmp_path / "final_proof_summary.json", {"final_status": "BLOCKED_BY_ENVIRONMENT"})
        return {"command": command, "returncode": 0, "status": "PASS", "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(full_proof_pass_attempt, "_run", fake_run)

    attempt = full_proof_pass_attempt.run_attempt(evidence_dir=tmp_path)

    assert attempt["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert ["docker", "compose", "up", "-d", "postgres", "qdrant"] not in commands
    assert (tmp_path / "full_proof_pass_attempt.md").is_file()


def test_attempt_starts_docker_when_route_is_docker_compose(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], timeout_seconds: int) -> dict[str, Any]:
        commands.append(command)
        if any("local_proof_doctor.py" in part for part in command):
            _write_json(tmp_path / "local_proof_doctor_report.json", _doctor_payload("PASS", "docker_compose"))
        if any("prove_final_product.py" in part for part in command):
            _write_json(tmp_path / "final_proof_summary.json", {"final_status": "PASS"})
        return {"command": command, "returncode": 0, "status": "PASS", "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(full_proof_pass_attempt, "_run", fake_run)

    attempt = full_proof_pass_attempt.run_attempt(evidence_dir=tmp_path)

    assert attempt["status"] == "PASS"
    assert ["docker", "compose", "up", "-d", "postgres", "qdrant"] in commands


def test_attempt_uses_external_services_without_docker_up(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], timeout_seconds: int) -> dict[str, Any]:
        commands.append(command)
        if any("local_proof_doctor.py" in part for part in command):
            _write_json(tmp_path / "local_proof_doctor_report.json", _doctor_payload("PASS", "external_services"))
        if any("prove_final_product.py" in part for part in command):
            _write_json(tmp_path / "final_proof_summary.json", {"final_status": "PASS"})
        return {"command": command, "returncode": 0, "status": "PASS", "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(full_proof_pass_attempt, "_run", fake_run)

    attempt = full_proof_pass_attempt.run_attempt(evidence_dir=tmp_path)

    assert attempt["status"] == "PASS"
    assert ["docker", "compose", "up", "-d", "postgres", "qdrant"] not in commands


def test_render_attempt_markdown_contains_status() -> None:
    markdown = full_proof_pass_attempt.render_attempt_markdown(
        {
            "status": "PASS",
            "generated_at": "2026-06-22T00:00:00+00:00",
            "can_retry_without_code_changes": False,
            "final_summary_path": "final_case_evidence/final_proof_summary.json",
            "doctor_report_path": "final_case_evidence/local_proof_doctor_report.json",
            "doctor": {
                "effective_service_route": "external_services",
                "recommended_route": "Use services",
                "human_summary": "Ready",
                "exact_commands": ["python scripts/prove_final_product.py --full --skip-live"],
            },
        },
        {"passed": 10, "failed": 0, "blocked_by_environment": 0},
    )

    assert "Status: `PASS`" in markdown
    assert "external_services" in markdown
