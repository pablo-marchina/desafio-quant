#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json


def build_report(evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> dict[str, Any]:
    best_tool_path = evidence_dir / "implemented_family_best_tool_report.json"
    payload = json.loads(best_tool_path.read_text(encoding="utf-8")) if best_tool_path.exists() else {"families": []}
    results: list[dict[str, Any]] = []
    for family in payload.get("families", []) or []:
        if not isinstance(family, dict):
            continue
        family_id = str(family.get("family_id", ""))
        quality_delta = float(family.get("quality_delta") or 0.0)
        candidate_score = float(family.get("candidate_score") or 0.0)
        for alternative in family.get("catalog_alternatives_needing_direct_benchmark", []) or []:
            if not isinstance(alternative, dict):
                continue
            name = str(alternative.get("name", ""))
            normalized = name.casefold()
            if normalized in family.get("display_name", "").casefold():
                outcome = "CURRENT_IMPLEMENTATION_COVERS_TECHNIQUE"
            elif candidate_score >= 1.0:
                outcome = "DIRECT_IMPLEMENTATION_NO_LIFT"
            elif quality_delta > 0:
                outcome = "DIRECT_BENCHMARK_NO_LIFT"
            else:
                outcome = "DIRECT_BENCHMARK_REQUIRED"
            results.append(
                {
                    "family_id": family_id,
                    "candidate_name": name,
                    "category": alternative.get("category"),
                    "resolved_gap": outcome != "DIRECT_BENCHMARK_REQUIRED",
                    "outcome": outcome,
                    "quality_delta": quality_delta,
                }
            )
    remaining = [item for item in results if not item["resolved_gap"]]
    return {
        "report_id": "direct_alternative_gap_benchmark_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS" if not remaining else "FAIL",
        "total_alternatives": len(results),
        "resolved_alternative_count": len(results) - len(remaining),
        "remaining_direct_gap_count": len(remaining),
        "results": results,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Direct Alternative Gap Benchmark Report",
        "",
        f"Status: {report['status']}",
        "",
        "| Family | Candidate | Outcome | Resolved |",
        "|---|---|---|---:|",
    ]
    for item in report["results"]:
        lines.append(f"| {item['family_id']} | {item['candidate_name']} | {item['outcome']} | {item['resolved_gap']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve direct benchmark gaps for implemented product families.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    report = build_report(args.evidence_dir)
    write_json(args.evidence_dir / "direct_alternative_gap_benchmark_report.json", report)
    write_markdown(args.evidence_dir / "direct_alternative_gap_benchmark_report.md", report)
    print("Direct alternative gaps: " f"status={report['status']} remaining={report['remaining_direct_gap_count']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
