#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.package_final_release import DEFAULT_ZIP_PATH, is_allowlisted, is_forbidden  # noqa: E402

DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the generated final release ZIP contents.")
    parser.add_argument("--zip-path", type=Path, default=DEFAULT_ZIP_PATH)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    report = check_final_release_zip(args.zip_path)
    write_zip_reports(args.evidence_dir, report)
    if report["status"] != "PASS":
        print(f"FAIL: final release ZIP is not clean: {args.zip_path}")
        for violation in report["violations"][:50]:
            print(f"  {violation['entry']}: {violation['reason']}")
        return 1
    print(f"PASS: final release ZIP clean: {args.zip_path}")
    return 0


def check_final_release_zip(zip_path: Path) -> dict[str, object]:
    generated_at = datetime.now(UTC).isoformat()
    if not zip_path.exists():
        return {
            "report_id": "final_release_zip_clean_report",
            "status": "FAIL",
            "generated_at": generated_at,
            "zip_path": str(zip_path),
            "violations": [{"entry": str(zip_path), "reason": "missing_zip"}],
            "entries": [],
        }
    with zipfile.ZipFile(zip_path) as archive:
        entries = sorted(item.filename for item in archive.infolist() if not item.is_dir())
    violations: list[dict[str, str]] = []
    for entry in entries:
        if is_forbidden(entry):
            violations.append({"entry": entry, "reason": "forbidden_artifact"})
        elif not is_allowlisted(entry):
            violations.append({"entry": entry, "reason": "not_allowlisted"})
    status = "PASS" if not violations else "FAIL"
    return {
        "report_id": "final_release_zip_clean_report",
        "status": status,
        "generated_at": generated_at,
        "zip_path": str(zip_path),
        "entry_count": len(entries),
        "violation_count": len(violations),
        "violations": violations,
        "entries": entries,
    }


def write_zip_reports(evidence_dir: Path, report: dict[str, object]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _write_json(evidence_dir / "final_release_zip_clean_report.json", report)
    _write_json(
        evidence_dir / "release_cleanliness_report.json",
        {
            "report_id": "release_cleanliness_report",
            "status": report["status"],
            "generated_at": report["generated_at"],
            "zip_path": report["zip_path"],
            "file_count": report.get("entry_count", 0),
            "forbidden_count": report.get("violation_count", 0),
            "forbidden_entries": report.get("violations", []),
        },
    )
    _write_cleanliness_markdown(evidence_dir / "release_cleanliness_report.md", report)
    forbidden_entries = [
        item["entry"]
        for item in report.get("violations", [])
        if isinstance(item, dict) and item.get("reason") == "forbidden_artifact"
    ]
    _write_json(
        evidence_dir / "final_release_forbidden_artifacts_report.json",
        {
            "report_id": "final_release_forbidden_artifacts_report",
            "status": "PASS" if not forbidden_entries else "FAIL",
            "generated_at": report["generated_at"],
            "forbidden_entries": forbidden_entries,
        },
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_cleanliness_markdown(path: Path, report: dict[str, object]) -> None:
    lines = [
        "# Release Cleanliness Report",
        "",
        f"Status: `{report['status']}`",
        f"ZIP path: `{report['zip_path']}`",
        f"Entry count: `{report.get('entry_count', 0)}`",
        f"Violations: `{report.get('violation_count', 0)}`",
        "",
    ]
    violations = report.get("violations", [])
    if isinstance(violations, list) and violations:
        for violation in violations:
            if isinstance(violation, dict):
                lines.append(f"- `{violation.get('entry')}`: {violation.get('reason')}")
    else:
        lines.append("No forbidden or non-allowlisted entries were found.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
