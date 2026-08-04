#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SAST with Bandit and write final evidence.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    started_at = datetime.now(UTC).isoformat()
    command = [sys.executable, "-m", "bandit", "-r", "src", "scripts", "-f", "json"]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = _build_report(command, started_at, result)
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    (args.evidence_dir / "sast_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"SAST_STATUS={payload['status']}")
    return 0 if payload["status"] in {"PASS", "WARN"} else 1


def _build_report(
    command: list[str],
    started_at: str,
    result: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    if result.returncode == 1 and "No module named bandit" in result.stderr:
        return {
            "report_id": "sast_report",
            "status": "BLOCKED_BY_ENVIRONMENT",
            "tool": "bandit",
            "version": "not_installed",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "command": " ".join(command),
            "findings_count": None,
            "reason": "Bandit is not installed.",
        }
    parsed = _parse_bandit_stdout(result.stdout)
    results = parsed.get("results", []) if isinstance(parsed, dict) else []
    high_count = sum(1 for finding in results if str(finding.get("issue_severity", "")).upper() == "HIGH")
    medium_count = sum(1 for finding in results if str(finding.get("issue_severity", "")).upper() == "MEDIUM")
    low_count = sum(1 for finding in results if str(finding.get("issue_severity", "")).upper() == "LOW")
    status = (
        "FAIL" if result.returncode not in {0, 1} or high_count else ("WARN" if medium_count or low_count else "PASS")
    )
    return {
        "report_id": "sast_report",
        "status": status,
        "tool": "bandit",
        "version": _version(),
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "command": " ".join(command),
        "returncode": result.returncode,
        "findings_count": len(results),
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def _parse_bandit_stdout(stdout: str) -> dict[str, Any]:
    try:
        parsed = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _version() -> str:
    result = subprocess.run([sys.executable, "-m", "bandit", "--version"], capture_output=True, text=True)
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
