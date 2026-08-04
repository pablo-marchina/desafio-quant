#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.review_free_external_candidates import DEFAULT_REGISTRY_PATH, ELIGIBLE_STATUSES, _load_registry
from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, read_csv, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Check external candidate free/no-cost verification coverage.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_EVIDENCE_DIR / "candidate_catalog.csv")
    parser.add_argument(
        "--report-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "external_free_verification_report.json"
    )
    parser.add_argument(
        "--markdown-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "external_free_verification_report.md"
    )
    args = parser.parse_args()

    report = build_verification_report(args.registry, args.catalog)
    write_json(args.report_path, report)
    write_markdown_report(args.markdown_path, report)
    print(
        "External free verification checked: "
        f"status={report['status']}, external_unique={report['summary']['external_unique_count']}, "
        f"eligible={report['summary']['ranking_eligible_count']}, "
        f"blocked={report['summary']['blocked_or_unverified_count']}"
    )
    return 0 if report["status"] == "PASS" else 1


def build_verification_report(registry_path: Path, catalog_path: Path) -> dict[str, Any]:
    rows = read_csv(catalog_path)
    registry = _load_registry(registry_path, rows)
    registry_entries = registry.get("entries", [])
    if not isinstance(registry_entries, list):
        raise ValueError("Registry entries must be a list.")
    external_rows = [row for row in rows if row.get("status") == "FUTURE_RESEARCH"]
    categories_by_name: dict[str, set[str]] = {}
    for row in external_rows:
        categories_by_name.setdefault(row.get("name", ""), set()).add(row.get("category", ""))
    entries_by_name = {str(entry.get("name", "")): entry for entry in registry_entries if isinstance(entry, dict)}
    items = [
        _build_item(name, sorted(categories), entries_by_name.get(name))
        for name, categories in categories_by_name.items()
    ]
    missing = [item for item in items if item["verification_status"] == "MISSING_REGISTRY_ENTRY"]
    missing_source = [
        item
        for item in items
        if item["verification_status"] != "MISSING_REGISTRY_ENTRY" and not item["official_source_url"]
    ]
    status = "PASS" if not missing and not missing_source else "FAIL"
    return {
        "report_id": "external_free_verification_report",
        "status": status,
        "registry_path": str(registry_path),
        "catalog_path": str(catalog_path),
        "policy": (
            "Every external FUTURE_RESEARCH candidate must have an explicit free/no-cost classification. "
            "Only eligible free/local/API statuses may enter benchmark ranking."
        ),
        "summary": {
            "external_row_count": len(external_rows),
            "external_unique_count": len(items),
            "registry_entry_count": len(registry_entries),
            "ranking_eligible_count": sum(1 for item in items if item["ranking_eligible"]),
            "blocked_or_unverified_count": sum(1 for item in items if not item["ranking_eligible"]),
            "missing_registry_count": len(missing),
            "missing_source_count": len(missing_source),
        },
        "items": sorted(items, key=lambda item: str(item["name"]).lower()),
    }


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# External Free Verification Report",
        "",
        f"Status: `{report['status']}`",
        "",
        f"- External rows: {summary['external_row_count']}",
        f"- External unique names: {summary['external_unique_count']}",
        f"- Ranking eligible: {summary['ranking_eligible_count']}",
        f"- Blocked or unverified: {summary['blocked_or_unverified_count']}",
        f"- Missing registry entries: {summary['missing_registry_count']}",
        f"- Missing official sources: {summary['missing_source_count']}",
        "",
        "| Candidate | Status | Eligible | Source | Categories |",
        "|---|---|---:|---|---|",
    ]
    for item in report["items"]:
        lines.append(
            f"| {_md_cell(str(item['name']))} | {item['verification_status']} | {item['ranking_eligible']} | "
            f"{_md_cell(str(item['official_source_url']))} | {_md_cell(', '.join(item['categories']))} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_item(name: str, categories: list[str], entry: dict[str, Any] | None) -> dict[str, Any]:
    if entry is None:
        return {
            "name": name,
            "categories": categories,
            "verification_status": "MISSING_REGISTRY_ENTRY",
            "ranking_eligible": False,
            "official_source_url": "",
            "free_tier_evidence": "",
            "benchmark_path": "",
        }
    status = str(entry.get("status", ""))
    return {
        "name": name,
        "categories": categories,
        "verification_status": status,
        "ranking_eligible": status in ELIGIBLE_STATUSES,
        "official_source_url": str(entry.get("official_source_url", "")),
        "free_tier_evidence": str(entry.get("free_tier_evidence", "")),
        "benchmark_path": str(entry.get("benchmark_path", "")),
        "env_vars": list(entry.get("env_vars", [])),
    }


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
