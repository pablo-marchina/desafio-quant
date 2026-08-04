#!/usr/bin/env python3
"""Build the final release package from scratch.

Usage: python scripts/build_final_release.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = PROJECT_ROOT / "release"
EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def main() -> int:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    steps = [
        ("Checking repository cleanliness", ["python", "scripts/check_repository_clean.py"]),
        (
            "Generating evidence pack",
            ["python", "scripts/generate_final_evidence_pack.py", "--evidence-dir", str(EVIDENCE_DIR)],
        ),
        ("Running security scans", ["python", "scripts/run_secret_scan.py", "--evidence-dir", str(EVIDENCE_DIR)]),
        ("Running SAST scan", ["python", "scripts/run_sast_scan.py", "--evidence-dir", str(EVIDENCE_DIR)]),
        ("Running dependency scan", ["python", "scripts/run_dependency_scan.py", "--evidence-dir", str(EVIDENCE_DIR)]),
        ("Generating SBOM", ["python", "scripts/generate_sbom.py", "--evidence-dir", str(EVIDENCE_DIR)]),
        ("Running container scan", ["python", "scripts/run_container_scan.py", "--evidence-dir", str(EVIDENCE_DIR)]),
        (
            "Running OpenSSF scorecard",
            ["python", "scripts/run_openssf_scorecard.py", "--evidence-dir", str(EVIDENCE_DIR)],
        ),
        (
            "Checking security release",
            ["python", "scripts/check_security_release.py", "--evidence-dir", str(EVIDENCE_DIR)],
        ),
        ("Checking no mock runtime", ["python", "scripts/check_no_mock_runtime.py"]),
        ("Checking no demo dependency", ["python", "scripts/check_no_demo_dependency.py"]),
        ("Building release ZIP", ["python", "scripts/package_final_release.py", "--evidence-dir", str(EVIDENCE_DIR)]),
        (
            "Verifying release ZIP",
            ["python", "scripts/check_final_release_zip.py", "--evidence-dir", str(EVIDENCE_DIR)],
        ),
    ]

    failures = []
    for description, command in steps:
        print(f"[{description}]...", end=" ")
        sys.stdout.flush()
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
        if result.returncode == 0:
            print("PASS")
        else:
            print("FAIL")
            failures.append(
                (description, result.returncode, result.stdout.strip()[-500:], result.stderr.strip()[-500:])
            )

    release_manifest = {
        "report_id": "final_build_release_manifest",
        "status": "PASS" if not failures else "FAIL",
        "steps_total": len(steps),
        "steps_passed": len(steps) - len(failures),
        "steps_failed": len(failures),
        "failures": [{"step": f, "returncode": rc, "stdout": out, "stderr": err} for f, rc, out, err in failures],
    }
    (EVIDENCE_DIR / "final_build_release_manifest.json").write_text(
        json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8"
    )

    if failures:
        print("\nFAIL: build-final-release")
        for f, rc, out, err in failures:
            print(f"  {f}: returncode={rc}")
            if out:
                print(f"    stdout: {out[:200]}")
            if err:
                print(f"    stderr: {err[:200]}")
        return 1

    print("\nPASS: build-final-release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
