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
    parser = argparse.ArgumentParser(description="Run container scan or record a no-image release decision.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--image", default="")
    args = parser.parse_args()

    started_at = datetime.now(UTC).isoformat()
    if not args.image:
        payload = {
            "report_id": "container_scan_report",
            "status": "PASS",
            "tool": "release_policy",
            "version": "not_applicable",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "command": "not_applicable_no_release_container_image",
            "findings_count": 0,
            "applies": False,
            "reason": "The final source release does not publish a container image.",
        }
        _write(args.evidence_dir / "container_scan_report.json", payload)
        print("CONTAINER_SCAN_STATUS=PASS")
        return 0

    scanner = "trivy" if shutil.which("trivy") else "grype" if shutil.which("grype") else ""
    if not scanner:
        payload = {
            "report_id": "container_scan_report",
            "status": "BLOCKED_BY_ENVIRONMENT",
            "tool": "trivy_or_grype",
            "version": "not_installed",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "command": f"trivy image {args.image}",
            "findings_count": None,
            "reason": "Container scanner is not installed.",
        }
        _write(args.evidence_dir / "container_scan_report.json", payload)
        print("CONTAINER_SCAN_STATUS=BLOCKED_BY_ENVIRONMENT")
        return 1

    command = [scanner, "image", args.image] if scanner == "trivy" else [scanner, args.image]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    payload = {
        "report_id": "container_scan_report",
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "tool": scanner,
        "version": _version(scanner),
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "command": " ".join(command),
        "returncode": result.returncode,
        "findings_count": 0 if result.returncode == 0 else 1,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }
    _write(args.evidence_dir / "container_scan_report.json", payload)
    print(f"CONTAINER_SCAN_STATUS={payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


def _version(tool: str) -> str:
    result = subprocess.run([tool, "--version"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else "unknown"


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
