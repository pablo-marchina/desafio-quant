#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local OpenSSF-style release scorecard checks.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    report = build_report(args.evidence_dir)
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    (args.evidence_dir / "openssf_scorecard_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OPENSSF_SCORECARD_STATUS={report['status']}")
    return 0 if report["status"] in {"PASS", "WARN"} else 1


def build_report(evidence_dir: Path) -> dict[str, Any]:
    checks = [
        _file_check("ci_workflow_present", ".github/workflows/ci.yml", 1.0, critical=True),
        _file_check("python_lock_or_project_metadata", "pyproject.toml", 1.0, critical=True),
        _file_check("frontend_lockfile_present", "frontend/package-lock.json", 1.0, critical=True),
        _file_check("security_policy_present", "SECURITY.md", 1.0, critical=False),
        _file_check("license_declared", "LICENSE", 0.5, critical=False),
        _report_status_check(evidence_dir, "secret_scan_report.json", 1.0, critical=True),
        _report_status_check(evidence_dir, "dependency_vulnerability_report.json", 1.0, critical=True),
        _report_status_check(evidence_dir, "sast_report.json", 1.0, critical=True, allowed_statuses={"PASS", "WARN"}),
        _report_status_check(evidence_dir, "sbom_report.json", 1.0, critical=True),
        _report_status_check(evidence_dir, "container_scan_report.json", 1.0, critical=True),
        _forbidden_path_check("no_committed_env_file", ".env", 1.0, critical=True),
        _forbidden_path_check("no_frontend_node_modules", "frontend/node_modules", 1.0, critical=True),
        _forbidden_path_check("no_local_product_db", "data/product/product.db", 1.0, critical=True),
    ]
    possible_score = sum(float(check["weight"]) for check in checks)
    achieved_score = sum(float(check["weight"]) for check in checks if check["passed"])
    score = round(achieved_score / possible_score, 4) if possible_score else 0.0
    critical_failures = [check for check in checks if check["critical"] and not check["passed"]]
    warnings = [check for check in checks if not check["critical"] and not check["passed"]]
    status = "FAIL" if critical_failures else "PASS"
    return {
        "report_id": "openssf_scorecard_report",
        "status": status,
        "tool": "local-openssf-style-scorecard",
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "score": score,
        "score_percent": round(score * 100.0, 2),
        "critical_failure_count": len(critical_failures),
        "warning_count": len(warnings),
        "checks": checks,
        "note": (
            "Local quantitative release scorecard used because the official OpenSSF scorecard binary is unavailable."
        ),
    }


def _file_check(check_id: str, relative_path: str, weight: float, *, critical: bool) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    return _check(check_id, path.exists(), weight, critical, {"path": relative_path, "exists": path.exists()})


def _forbidden_path_check(check_id: str, relative_path: str, weight: float, *, critical: bool) -> dict[str, Any]:
    tracked = _git_tracks(relative_path)
    return _check(check_id, not tracked, weight, critical, {"path": relative_path, "git_tracked": tracked})


def _report_status_check(
    evidence_dir: Path,
    report_name: str,
    weight: float,
    *,
    critical: bool,
    allowed_statuses: set[str] | None = None,
) -> dict[str, Any]:
    allowed = allowed_statuses or {"PASS"}
    path = evidence_dir / report_name
    status = "MISSING"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = str(payload.get("status", "NOT_RUN"))
        except json.JSONDecodeError:
            status = "INVALID_JSON"
    return _check(
        f"report.{report_name}",
        status in allowed,
        weight,
        critical,
        {"report": report_name, "status": status, "allowed_statuses": sorted(allowed)},
    )


def _check(check_id: str, passed: bool, weight: float, critical: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "critical": critical,
        "weight": weight,
        "score": weight if passed else 0.0,
        "details": details,
    }


def _git_tracks(relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
