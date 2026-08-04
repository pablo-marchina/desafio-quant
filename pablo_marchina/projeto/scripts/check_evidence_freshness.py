#!/usr/bin/env python3
"""Check that final evidence artifacts are not stale relative to source reports.

Fails if:
- Individual report is newer than the summary/resolution.
- NO_GO coexists with PASS reports.
- Conflicting status between final files.
- Evidence timestamp is older than the last relevant commit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"

REQUIRED_FINAL_FILES = [
    "final_product_go_no_go_report.json",
    "final_proof_summary.json",
    "product_readiness_report.json",
]

SOURCE_REPORT_PREFIXES = [
    "secret_scan_report",
    "dependency_vulnerability_report",
    "sast_report",
    "sbom_report",
    "container_scan_report",
    "openssf_scorecard_report",
    "security_scan_report",
]


def _get_mtime(path: Path) -> float:
    return path.stat().st_mtime


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _last_commit_time() -> float:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return float(result.stdout.strip())
    return 0.0


def main() -> int:
    failures: list[str] = []

    if not EVIDENCE_DIR.exists():
        print("FAIL: evidence directory does not exist")
        return 1

    last_commit = _last_commit_time()
    if last_commit > 0:
        for final_file in REQUIRED_FINAL_FILES:
            path = EVIDENCE_DIR / final_file
            if path.exists():
                if _get_mtime(path) < last_commit:
                    failures.append(
                        f"{final_file} is older than last commit "
                        f"(mtime={_get_mtime(path):.0f} < commit={last_commit:.0f})"
                    )

    final_report = EVIDENCE_DIR / "final_product_go_no_go_report.json"
    if final_report.exists():
        go_report = _load_json(final_report)
        go_status = go_report.get("status", "")
        if go_status == "NO_GO":
            for prefix in SOURCE_REPORT_PREFIXES:
                src_path = EVIDENCE_DIR / f"{prefix}.json"
                if src_path.exists():
                    src = _load_json(src_path)
                    if src.get("status") == "PASS":
                        failures.append(f"NO_GO in final report but {prefix}.json has PASS status")

    summary_file = EVIDENCE_DIR / "final_proof_summary.json"
    if summary_file.exists():
        summary = _load_json(summary_file)
        summary_time = _get_mtime(summary_file)
        for result in summary.get("results", []):
            label = result.get("label", "")
            if "generate_" in label or "run_" in label:
                continue
            for prefix in SOURCE_REPORT_PREFIXES:
                if prefix in label:
                    src_path = EVIDENCE_DIR / f"{prefix}.json"
                    if src_path.exists() and _get_mtime(src_path) > summary_time:
                        failures.append(
                            f"{prefix}.json is newer than final_proof_summary.json " f"(report should be regenerated)"
                        )

    go_report_path = EVIDENCE_DIR / "final_product_go_no_go_report.json"
    summary_path = EVIDENCE_DIR / "final_proof_summary.json"
    if go_report_path.exists() and summary_path.exists():
        go_report = _load_json(go_report_path)
        summary = _load_json(summary_path)
        go_final = go_report.get("final_status", "")
        summary_final = summary.get("final_status", "")
        if go_final != summary_final:
            failures.append(
                f"Status conflict: go_report.final_status={go_final} " f"vs proof_summary.final_status={summary_final}"
            )
        go_passed = go_report.get("passed", 0)
        summary_passed = summary.get("passed", 0)
        if go_passed != summary_passed:
            failures.append(
                f"Gate count conflict: go_report.passed={go_passed} " f"vs proof_summary.passed={summary_passed}"
            )

    if failures:
        print("FAIL: evidence freshness checks")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("PASS: evidence freshness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
