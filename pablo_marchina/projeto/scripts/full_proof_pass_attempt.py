#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR


def run_attempt(
    *,
    evidence_dir: Path,
    include_live: bool = False,
    require_docker_compose: bool = False,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    doctor = _run(
        [
            sys.executable,
            "scripts/local_proof_doctor.py",
            "--evidence-dir",
            str(evidence_dir),
            *(["--require-docker-compose"] if require_docker_compose else []),
        ],
        timeout_seconds=180,
    )
    doctor_payload = _read_json(evidence_dir / "local_proof_doctor_report.json")
    docker_up: dict[str, Any] | None = None
    route = doctor_payload.get("effective_service_route")
    if route == "docker_compose":
        docker_up = _run(["docker", "compose", "up", "-d", "postgres", "qdrant"], timeout_seconds=180)

    prove_command = [sys.executable, "scripts/prove_final_product.py", "--full"]
    if not include_live:
        prove_command.append("--skip-live")
    if require_docker_compose:
        prove_command.append("--require-docker-compose")
    prove = _run(prove_command, timeout_seconds=timeout_seconds)
    final_summary = _read_json(evidence_dir / "final_proof_summary.json")
    final_status = str(final_summary.get("final_status", "FAIL"))
    attempt = {
        "report_id": "full_proof_pass_attempt",
        "status": final_status,
        "generated_at": datetime.now(UTC).isoformat(),
        "include_live": include_live,
        "require_docker_compose": require_docker_compose,
        "doctor": _project_doctor(doctor, doctor_payload),
        "docker_compose_up": docker_up,
        "prove_final_product": _project_command(prove),
        "final_summary_path": str(evidence_dir / "final_proof_summary.json"),
        "doctor_report_path": str(evidence_dir / "local_proof_doctor_report.json"),
        "can_retry_without_code_changes": final_status == "BLOCKED_BY_ENVIRONMENT"
        and bool(doctor_payload.get("can_retry_without_code_changes", False)),
    }
    markdown = render_attempt_markdown(attempt, final_summary)
    (evidence_dir / "full_proof_pass_attempt.md").write_text(markdown, encoding="utf-8")
    return attempt


def render_attempt_markdown(attempt: dict[str, Any], final_summary: dict[str, Any]) -> str:
    doctor = attempt["doctor"]
    lines = [
        "# Full Proof PASS Attempt",
        "",
        f"Status: `{attempt['status']}`",
        f"Generated at: `{attempt['generated_at']}`",
        f"Doctor route: `{doctor.get('effective_service_route')}`",
        f"Recommended route: {doctor.get('recommended_route', '')}",
        f"Retry without code changes: `{attempt['can_retry_without_code_changes']}`",
        "",
        str(doctor.get("human_summary") or ""),
        "",
        "## Exact Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in doctor.get("exact_commands", []))
    lines.extend(
        [
            "",
            "## Proof Result",
            "",
            f"- Passed gates: `{final_summary.get('passed', 0)}`",
            f"- Failed gates: `{final_summary.get('failed', 0)}`",
            f"- Blocked by environment: `{final_summary.get('blocked_by_environment', 0)}`",
            f"- Final summary: `{attempt['final_summary_path']}`",
            f"- Doctor report: `{attempt['doctor_report_path']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _run(command: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "status": "BLOCKED_BY_ENVIRONMENT",
            "stdout_tail": "",
            "stderr_tail": f"Timed out after {exc.timeout} seconds.",
        }
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return {
        "command": command,
        "returncode": result.returncode,
        "status": "PASS" if result.returncode == 0 else "BLOCKED_BY_ENVIRONMENT",
        "stdout_tail": result.stdout[-3000:],
        "stderr_tail": result.stderr[-3000:],
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _project_doctor(command_result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    projected = _project_command(command_result)
    projected.update(
        {
            "status": payload.get("status", projected["status"]),
            "effective_service_route": payload.get("effective_service_route"),
            "recommended_route": payload.get("recommended_route"),
            "human_summary": payload.get("human_summary"),
            "exact_commands": payload.get("exact_commands", []),
        }
    )
    return projected


def _project_command(command_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": " ".join(command_result.get("command", [])),
        "returncode": command_result.get("returncode"),
        "status": command_result.get("status"),
        "stdout_tail": command_result.get("stdout_tail", ""),
        "stderr_tail": command_result.get("stderr_tail", ""),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attempt a reproducible full product proof PASS.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--require-docker-compose", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    attempt = run_attempt(
        evidence_dir=args.evidence_dir,
        include_live=args.include_live,
        require_docker_compose=args.require_docker_compose,
        timeout_seconds=args.timeout_seconds,
    )
    print(f"FULL_PROOF_PASS_ATTEMPT_STATUS={attempt['status']}")
    return 1 if attempt["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
