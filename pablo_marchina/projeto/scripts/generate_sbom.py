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
    parser = argparse.ArgumentParser(description="Generate an SBOM with a real SBOM tool when available.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    started_at = datetime.now(UTC).isoformat()
    if shutil.which("syft"):
        command = ["syft", str(PROJECT_ROOT), "-o", "cyclonedx-json"]
        tool = "syft"
    elif shutil.which("cyclonedx-py"):
        command = ["cyclonedx-py", "environment", "--of", "json"]
        tool = "cyclonedx-py"
    else:
        payload = {
            "report_id": "sbom_report",
            "status": "BLOCKED_BY_ENVIRONMENT",
            "tool": "syft_or_cyclonedx-py",
            "version": "not_installed",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "command": "syft . -o cyclonedx-json",
            "findings_count": None,
            "reason": "No SBOM generator is installed.",
        }
        _write_reports(args.evidence_dir, payload)
        print("SBOM_STATUS=BLOCKED_BY_ENVIRONMENT")
        return 1

    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = {
        "report_id": "sbom_report",
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "tool": tool,
        "version": _version(tool),
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "command": " ".join(command),
        "returncode": result.returncode,
        "findings_count": 0 if result.returncode == 0 else 1,
        "sbom_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }
    _write_reports(args.evidence_dir, payload)
    print(f"SBOM_STATUS={payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


def _version(tool: str) -> str:
    result = subprocess.run([tool, "--version"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else "unknown"


def _write_reports(evidence_dir: Path, payload: dict[str, object]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name in ("sbom_report.json", "sbom.json"):
        (evidence_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
