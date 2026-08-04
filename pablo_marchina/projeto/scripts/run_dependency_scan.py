#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Python and frontend dependency vulnerability scans.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    reports = [_pip_audit(), _npm_audit()]
    status = "PASS" if all(report["status"] == "PASS" for report in reports) else "BLOCKED_BY_ENVIRONMENT"
    if any(report["status"] == "FAIL" for report in reports):
        status = "FAIL"
    payload = {
        "report_id": "dependency_vulnerability_report",
        "status": status,
        "tool": "pip-audit+npm-audit",
        "version": "; ".join(str(report.get("version", "unknown")) for report in reports),
        "started_at": reports[0]["started_at"],
        "finished_at": datetime.now(UTC).isoformat(),
        "command": "pip-audit && npm audit --audit-level=high",
        "findings_count": sum(int(report.get("findings_count") or 0) for report in reports),
        "reports": reports,
    }
    _write(args.evidence_dir / "dependency_vulnerability_report.json", payload)
    print(f"DEPENDENCY_SCAN_STATUS={status}")
    return 0 if status == "PASS" else 1


def _pip_audit() -> dict[str, object]:
    started_at = datetime.now(UTC).isoformat()
    _generate_prod_reqs()
    prod_reqs = PROJECT_ROOT / ".pytest_tmp_final" / "prod_requirements.txt"
    pip_audit_bin = shutil.which("pip-audit")
    if not pip_audit_bin:
        return _blocked(
            "pip-audit",
            started_at,
            "pip-audit is not installed.",
            ["pip-audit", "--format", "json", "-r", str(prod_reqs)],
        )
    command = [pip_audit_bin, "--format", "json", "-r", str(prod_reqs)]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)
    return _report("pip-audit", command, started_at, result)


def _generate_prod_reqs() -> None:
    import tomllib

    reqs_dir = PROJECT_ROOT / ".pytest_tmp_final"
    reqs_dir.mkdir(parents=True, exist_ok=True)
    reqs_file = reqs_dir / "prod_requirements.txt"
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    deps = data["project"]["dependencies"]
    lines = []
    for dep in deps:
        import re

        name = re.split(r"[>=<~!]", dep)[0].strip()
        if name:
            lines.append(name)
    reqs_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _npm_audit() -> dict[str, object]:
    started_at = datetime.now(UTC).isoformat()
    npm = shutil.which("npm")
    if not npm:
        return _blocked("npm-audit", started_at, "npm is not installed.", ["npm", "audit", "--audit-level=high"])
    command = [npm, "audit", "--audit-level=high", "--json"]
    result = subprocess.run(command, cwd=PROJECT_ROOT / "frontend", capture_output=True, text=True)
    return _report("npm-audit", command, started_at, result)


def _report(
    tool: str,
    command: list[str],
    started_at: str,
    result: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    status = "PASS" if result.returncode == 0 else "FAIL"
    findings_count = _findings_count(tool, result.stdout, status)
    return {
        "status": status,
        "tool": tool,
        "version": _version(tool),
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "command": " ".join(command),
        "returncode": result.returncode,
        "findings_count": findings_count,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def _findings_count(tool: str, stdout: str, status: str) -> int:
    if status == "PASS":
        return 0
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return 1
    if tool == "pip-audit":
        return sum(len(dep.get("vulns", [])) for dep in payload.get("dependencies", []))
    if tool == "npm-audit":
        metadata = payload.get("metadata", {})
        vulnerabilities = metadata.get("vulnerabilities", {})
        return int(vulnerabilities.get("total", 1))
    return 1


def _blocked(tool: str, started_at: str, reason: str, command: list[str]) -> dict[str, object]:
    return {
        "status": "BLOCKED_BY_ENVIRONMENT",
        "tool": tool,
        "version": "not_installed",
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "command": " ".join(command),
        "findings_count": None,
        "reason": reason,
    }


def _version(tool: str) -> str:
    if tool == "pip-audit":
        pip_audit_bin = shutil.which("pip-audit")
        command = [pip_audit_bin or "pip-audit", "--version"]
    else:
        npm = shutil.which("npm")
        command = [npm or "npm", "--version"]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else "unknown"


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
