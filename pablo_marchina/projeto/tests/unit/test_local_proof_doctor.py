from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import local_proof_doctor


def _check(check_id: str, status: str) -> dict[str, Any]:
    return local_proof_doctor.make_check(
        check_id=check_id,
        component=check_id,
        status=status,
    )


def _baseline_checks(*, docker: str, postgres: str, qdrant: str, embedding: str) -> list[dict[str, Any]]:
    return [
        _check("docker_cli", docker),
        _check("docker_compose", docker),
        _check("postgres_connection", postgres),
        _check("qdrant_service", qdrant),
        _check("alembic_configuration", local_proof_doctor.PASS),
        _check("nvidia_corpus", local_proof_doctor.PASS),
        _check("embedding_provider", embedding),
    ]


def test_doctor_passes_with_external_services_when_docker_is_blocked() -> None:
    checks = _baseline_checks(
        docker=local_proof_doctor.BLOCKED,
        postgres=local_proof_doctor.PASS,
        qdrant=local_proof_doctor.PASS,
        embedding=local_proof_doctor.PASS,
    )

    status = local_proof_doctor.aggregate_doctor_status(
        checks,
        require_docker_compose=False,
        external_services_ok=True,
    )
    route = local_proof_doctor.resolve_service_route(
        checks,
        require_docker_compose=False,
        external_services_ok=True,
    )

    assert status == local_proof_doctor.PASS
    assert route == "external_services"


def test_doctor_blocks_when_no_docker_or_external_services() -> None:
    checks = _baseline_checks(
        docker=local_proof_doctor.BLOCKED,
        postgres=local_proof_doctor.BLOCKED,
        qdrant=local_proof_doctor.BLOCKED,
        embedding=local_proof_doctor.PASS,
    )

    status = local_proof_doctor.aggregate_doctor_status(
        checks,
        require_docker_compose=False,
        external_services_ok=True,
    )

    assert status == local_proof_doctor.BLOCKED


def test_doctor_require_docker_blocks_even_with_external_services() -> None:
    checks = _baseline_checks(
        docker=local_proof_doctor.BLOCKED,
        postgres=local_proof_doctor.PASS,
        qdrant=local_proof_doctor.PASS,
        embedding=local_proof_doctor.PASS,
    )

    status = local_proof_doctor.aggregate_doctor_status(
        checks,
        require_docker_compose=True,
        external_services_ok=True,
    )
    route = local_proof_doctor.resolve_service_route(
        checks,
        require_docker_compose=True,
        external_services_ok=True,
    )

    assert status == local_proof_doctor.BLOCKED
    assert route == "blocked_require_docker_compose"


def test_doctor_blocks_when_real_embedding_provider_is_missing() -> None:
    checks = _baseline_checks(
        docker=local_proof_doctor.PASS,
        postgres=local_proof_doctor.BLOCKED,
        qdrant=local_proof_doctor.BLOCKED,
        embedding=local_proof_doctor.BLOCKED,
    )

    status = local_proof_doctor.aggregate_doctor_status(
        checks,
        require_docker_compose=False,
        external_services_ok=True,
    )

    assert status == local_proof_doctor.BLOCKED


def test_doctor_cli_writes_report(monkeypatch, tmp_path: Path) -> None:
    payload = {
        "report_id": "local_proof_doctor_report",
        "status": local_proof_doctor.BLOCKED,
        "effective_service_route": "blocked_no_service_route",
        "blocking_checks": [],
        "checks": [],
    }

    def fake_run_doctor(**kwargs: object) -> dict[str, Any]:
        evidence_dir = kwargs["evidence_dir"]
        assert isinstance(evidence_dir, Path)
        local_proof_doctor.write_json(evidence_dir / "local_proof_doctor_report.json", payload)
        return payload

    monkeypatch.setattr(local_proof_doctor, "run_doctor", fake_run_doctor)

    exit_code = local_proof_doctor.main(["--evidence-dir", str(tmp_path)])

    assert exit_code == 0
    written = json.loads((tmp_path / "local_proof_doctor_report.json").read_text(encoding="utf-8"))
    assert written["status"] == local_proof_doctor.BLOCKED


def test_doctor_guidance_for_blocked_environment() -> None:
    checks = _baseline_checks(
        docker=local_proof_doctor.BLOCKED,
        postgres=local_proof_doctor.BLOCKED,
        qdrant=local_proof_doctor.BLOCKED,
        embedding=local_proof_doctor.PASS,
    )
    route = local_proof_doctor.resolve_service_route(
        checks,
        require_docker_compose=False,
        external_services_ok=True,
    )
    payload = {
        "status": local_proof_doctor.BLOCKED,
        "effective_service_route": route,
        "recommended_route": local_proof_doctor.recommend_route(checks, route),
        "exact_commands": local_proof_doctor.build_exact_commands(route),
        "environment_fix_required": True,
        "can_retry_without_code_changes": True,
        "blocking_checks": [check for check in checks if check["status"] == local_proof_doctor.BLOCKED],
    }
    payload["human_summary"] = local_proof_doctor.build_human_summary(payload)

    assert payload["recommended_route"].startswith("Fix Docker access")
    assert "docker compose up -d postgres qdrant" in payload["exact_commands"]
    assert "blocked by environment" in payload["human_summary"]
    assert "Local Proof Doctor" in local_proof_doctor.render_doctor_markdown(payload)


def test_doctor_guidance_for_external_services() -> None:
    checks = _baseline_checks(
        docker=local_proof_doctor.BLOCKED,
        postgres=local_proof_doctor.PASS,
        qdrant=local_proof_doctor.PASS,
        embedding=local_proof_doctor.PASS,
    )
    route = local_proof_doctor.resolve_service_route(
        checks,
        require_docker_compose=False,
        external_services_ok=True,
    )

    assert route == "external_services"
    assert local_proof_doctor.recommend_route(checks, route).startswith("Use already-running")
    assert any(command.startswith("set PRODUCT_DB_URL") for command in local_proof_doctor.build_exact_commands(route))
