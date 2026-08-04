#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, read_csv, write_json

DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "docs" / "free_external_candidate_registry.json"
ELIGIBLE_STATUS = "FREE_EXTERNAL_BENCHMARKABLE"
ELIGIBLE_STATUSES = frozenset(
    {
        "FREE_EXTERNAL_BENCHMARKABLE",
        "FREE_API_BENCHMARKABLE",
        "FREE_LOCAL_SUBSTITUTE",
        "INTERNAL_LOCAL_BENCHMARKABLE",
    }
)
VERIFICATION_STATUS = "NEEDS_FREE_TIER_VERIFICATION"


def main() -> int:
    parser = argparse.ArgumentParser(description="Review free external candidate benchmark eligibility.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_EVIDENCE_DIR / "candidate_catalog.csv")
    parser.add_argument(
        "--report-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "free_external_candidate_review.json"
    )
    parser.add_argument(
        "--markdown-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "free_external_candidate_review.md"
    )
    args = parser.parse_args()

    report = build_review_report(args.registry, args.catalog)
    write_json(args.report_path, report)
    write_markdown_report(args.markdown_path, report)
    print(
        "Free external candidates reviewed: "
        f"eligible={report['summary']['ranking_eligible_count']}, "
        f"needs_verification={report['summary']['needs_verification_count']}, "
        f"matched={report['summary']['matched_catalog_count']}"
    )
    return 0 if report["status"] == "PASS" else 1


def build_review_report(registry_path: Path, catalog_path: Path) -> dict[str, Any]:
    catalog_rows = read_csv(catalog_path) if catalog_path.exists() else []
    registry = _load_registry(registry_path, catalog_rows)
    catalog_by_name = {row.get("name", ""): row for row in catalog_rows}
    items = [_review_entry(entry, catalog_by_name.get(str(entry.get("name", "")))) for entry in registry["entries"]]
    summary = {
        "registry_count": len(items),
        "matched_catalog_count": sum(1 for item in items if item["catalog_match"]),
        "ranking_eligible_count": sum(1 for item in items if item["ranking_eligible"]),
        "needs_verification_count": sum(1 for item in items if item["status"] == VERIFICATION_STATUS),
        "not_in_catalog_count": sum(1 for item in items if not item["catalog_match"]),
    }
    return {
        "report_id": "free_external_candidate_review",
        "status": "PASS",
        "policy_ref": registry.get("policy_ref", "docs/final_benchmark_first_policy.md"),
        "registry_path": str(registry_path),
        "catalog_path": str(catalog_path),
        "selection_rule": (
            "FREE_EXTERNAL_BENCHMARKABLE, FREE_API_BENCHMARKABLE, FREE_LOCAL_SUBSTITUTE, and "
            "INTERNAL_LOCAL_BENCHMARKABLE entries may enter the ranked benchmark queue. "
            "NEEDS_FREE_TIER_VERIFICATION and PAID_OR_TRIAL_ONLY entries remain blocked until current "
            "terms, free/no-cost access, rate limits, and data-rights constraints are documented."
        ),
        "summary": summary,
        "ranking_eligible_names": sorted(str(item["name"]) for item in items if item["ranking_eligible"]),
        "items": items,
    }


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# Free External Candidate Review",
        "",
        f"Status: `{report['status']}`",
        "",
        f"- Registry entries: {summary['registry_count']}",
        f"- Matched catalog entries: {summary['matched_catalog_count']}",
        f"- Ranking eligible: {summary['ranking_eligible_count']}",
        f"- Needs free-tier verification: {summary['needs_verification_count']}",
        f"- Not in catalog: {summary['not_in_catalog_count']}",
        "",
        "| Candidate | Status | Catalog | Ranking eligible | Benchmark path |",
        "|---|---|---:|---:|---|",
    ]
    for item in report["items"]:
        lines.append(
            f"| {_md_cell(str(item['name']))} | {item['status']} | {item['catalog_match']} | "
            f"{item['ranking_eligible']} | {_md_cell(str(item['benchmark_path']))} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _review_entry(entry: dict[str, Any], catalog_row: dict[str, str] | None) -> dict[str, Any]:
    status = str(entry.get("status", "")).strip()
    catalog_status = catalog_row.get("status", "") if catalog_row else "NOT_IN_CATALOG"
    ranking_eligible = status in ELIGIBLE_STATUSES and catalog_row is not None
    return {
        "name": str(entry.get("name", "")),
        "status": status,
        "catalog_match": catalog_row is not None,
        "catalog_status": catalog_status,
        "ranking_eligible": ranking_eligible,
        "output_value_family": str(entry.get("output_value_family", "")),
        "free_tier_evidence": str(entry.get("free_tier_evidence", "")),
        "official_source_url": str(entry.get("official_source_url", "")),
        "benchmark_path": str(entry.get("benchmark_path", "")),
        "env_vars": list(entry.get("env_vars", [])),
        "terms_review_required": bool(entry.get("terms_review_required", True)),
        "local_test_behavior": str(entry.get("local_test_behavior", "")),
        "promotion_guardrail": (
            "Registry eligibility permits benchmark ranking only; runtime promotion still requires direct "
            "output-quality lift, cost/latency/risk evidence, and decision-ledger approval."
        ),
    }


def _load_registry(path: Path, catalog_rows: list[dict[str, str]] | None = None) -> dict[str, Any]:
    if not path.exists():
        return _derive_registry_from_catalog(catalog_rows or [])
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"Registry must contain an entries list: {path}")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"Registry entry {index} must be an object")
        if not entry.get("name") or not entry.get("status") or not entry.get("benchmark_path"):
            raise ValueError(f"Registry entry {index} is missing name, status, or benchmark_path")
    return payload


def _derive_registry_from_catalog(catalog_rows: list[dict[str, str]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in catalog_rows:
        name = row.get("name", "").strip()
        if not name or name in seen:
            continue
        status = row.get("status", "")
        required = " ".join(
            row.get(key, "")
            for key in (
                "required_configuration",
                "external_dependency",
                "substitute_reason",
                "cost_policy",
            )
        ).casefold()
        if status == "FUTURE_RESEARCH" or any(
            marker in required for marker in ("external", "paid", "license", "credential", "hardware", "api key")
        ):
            verification = row.get("free_self_hosted_verification", "").strip()
            if "pass" in verification.casefold() or "free" in required or "self" in required:
                registry_status = "FREE_LOCAL_SUBSTITUTE"
            else:
                registry_status = VERIFICATION_STATUS
            entries.append(
                {
                    "name": name,
                    "status": registry_status,
                    "official_source_url": row.get("source_or_reference", "") or "candidate_catalog_maximal_final_complementary_governed(1).csv",
                    "free_tier_evidence": verification or row.get("cost_policy", ""),
                    "benchmark_path": row.get("benchmark", "") or "scripts/run_benchmark.py --suite complete-catalog",
                    "env_vars": [],
                    "terms_review_required": registry_status == VERIFICATION_STATUS,
                    "local_test_behavior": "derived_from_governed_candidate_catalog",
                }
            )
            seen.add(name)
    return {
        "policy_ref": "candidate_catalog_maximal_final_complementary_governed(1).csv",
        "entries": entries,
        "derived_from_catalog": True,
    }


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
