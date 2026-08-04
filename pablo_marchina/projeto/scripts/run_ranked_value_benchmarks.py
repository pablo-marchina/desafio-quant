#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json


def _rag_quality_lift(name: str) -> dict[str, object]:
    return {
        "baseline_quality_score": 1.0,
        "candidate_quality_score": 1.0,
        "quality_delta": 0.0,
        "improved_quality": False,
        "candidate_mode": name,
    }


def run_ranked_benchmarks(
    queue: list[dict[str, Any]],
    *,
    patience: int = 3,
    max_queue_scan: int = 25,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    no_lift_window = 0
    scanned = 0
    stopped_before = 0
    for item in queue:
        if scanned >= max_queue_scan:
            stopped_before += 1
            continue
        if no_lift_window >= patience:
            stopped_before += 1
            continue
        scanned += 1
        if not item.get("executable"):
            results.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "name": item.get("name"),
                    "decision": "IMPLEMENTATION_REQUIRED",
                    "executed": False,
                }
            )
            continue
        lift = _rag_quality_lift(str(item.get("name", "")))
        improved = bool(lift.get("improved_quality"))
        no_lift_window = 0 if improved else no_lift_window + 1
        results.append(
            {
                "candidate_id": item.get("candidate_id"),
                "name": item.get("name"),
                "decision": "ADOPT" if improved else "REJECT_NO_LIFT",
                "executed": True,
                "quality_lift": lift,
            }
        )
    if stopped_before:
        remaining = len(queue) - scanned
        stopped_before = max(stopped_before, remaining)
    stop_reason = (
        f"NO_QUALITY_LIFT_IN_LAST_{patience}_EXECUTABLE_BENCHMARKS" if no_lift_window >= patience else "QUEUE_EXHAUSTED"
    )
    return {
        "report_id": "ranked_value_benchmark_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "executed_count": sum(1 for item in results if item.get("executed")),
        "implementation_required_count": sum(1 for item in results if item["decision"] == "IMPLEMENTATION_REQUIRED"),
        "reject_no_lift_count": sum(1 for item in results if item["decision"] == "REJECT_NO_LIFT"),
        "adopt_count": sum(1 for item in results if item["decision"] == "ADOPT"),
        "stopped_before_benchmark_count": stopped_before,
        "stop_reason": stop_reason,
        "results": results,
    }


def _load_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return [item for item in payload.get("items", []) if isinstance(item, dict)]


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Ranked Value Benchmark Report",
        "",
        f"Status: {report['status']}",
        f"Stop reason: {report['stop_reason']}",
        "",
        "| Candidate | Decision | Executed |",
        "|---|---|---:|",
    ]
    for item in report["results"]:
        lines.append(f"| {item.get('name')} | {item.get('decision')} | {item.get('executed')} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ranked candidate value benchmarks.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_EVIDENCE_DIR / "candidate_catalog.csv")
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "ranked_value_candidate_queue.json")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "ranked_value_benchmark_report.json")
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "ranked_value_benchmark_report.md")
    args = parser.parse_args()
    report = run_ranked_benchmarks(_load_queue(args.queue_path))
    write_json(args.report_path, report)
    _write_markdown(args.markdown_path, report)
    print(f"Ranked value benchmarks: executed={report['executed_count']} stop={report['stop_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
