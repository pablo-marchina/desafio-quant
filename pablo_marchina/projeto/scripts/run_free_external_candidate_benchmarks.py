#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

TOOL_PROBES: dict[str, dict[str, Any]] = {
    "OpenSSF Scorecard": {
        "commands": ["scorecard"],
        "version_commands": [["scorecard", "--version"]],
        "metrics": ["supply_chain_risk_delta", "repository_hardening_findings"],
        "activation": ["Install OpenSSF Scorecard and rerun this gate."],
    },
    "Renovate": {
        "commands": ["renovate.cmd", "renovate"],
        "version_commands": [["renovate", "--version"], ["renovate.cmd", "--version"]],
        "metrics": ["actionable_dependency_updates", "security_update_coverage"],
        "activation": ["Install Renovate CLI or configure hosted Renovate."],
    },
    "Argilla": {
        "modules": ["argilla"],
        "metrics": ["human_feedback_capture", "label_quality"],
        "activation": ["Install argilla and configure a local/free workspace."],
    },
    "Phoenix": {
        "modules": ["phoenix", "arize.phoenix"],
        "commands": ["phoenix"],
        "metrics": ["trace_coverage", "evaluation_observability"],
        "activation": ["Install arize-phoenix or enable the optional compose profile."],
    },
}


def build_probe_report(review_path: Path) -> dict[str, Any]:
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {"items": []}
    eligible = [item for item in review.get("items", []) if isinstance(item, dict) and item.get("ranking_eligible")]
    probes = [_probe_item(item) for item in eligible]
    ready = sum(1 for item in probes if item["status"] == "READY_FOR_PRODUCT_BENCHMARK")
    blocked = sum(1 for item in probes if item["status"] == "BLOCKED_BY_ENVIRONMENT")
    return {
        "report_id": "free_external_candidate_benchmark_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "PASS",
        "summary": {
            "eligible_candidate_count": len(eligible),
            "ready_for_product_benchmark_count": ready,
            "blocked_by_environment_count": blocked,
        },
        "probes": probes,
    }


def _probe_item(item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get("name", ""))
    spec = TOOL_PROBES.get(name, {})
    commands = list(spec.get("commands", []))
    modules = list(spec.get("modules", []))
    commands_found = [command for command in commands if shutil.which(command)]
    modules_found = [module for module in modules if _module_available(module)]
    version_checks = [_version_check(command) for command in spec.get("version_commands", [])]
    ready = bool(commands_found or modules_found or any(check["available"] for check in version_checks))
    return {
        "name": name,
        "status": "READY_FOR_PRODUCT_BENCHMARK" if ready else "BLOCKED_BY_ENVIRONMENT",
        "decision": "PRODUCT_BENCHMARK_REQUIRED" if ready else "BLOCKED_BY_ENVIRONMENT",
        "reason": "Tool/module found." if ready else "Required free/local tool is not installed in this environment.",
        "quality_delta": None,
        "value_hypothesis": _value_hypothesis(name, item),
        "output_quality_metrics": spec.get("metrics", ["output_quality_delta", "risk_delta"]),
        "benchmark_command": f"python scripts/run_free_external_candidate_benchmarks.py --candidate {name}",
        "activation_commands": spec.get("activation", [f"Install and configure {name}."]),
        "commands_found": commands_found,
        "modules_found": modules_found,
        "version_checks": version_checks,
    }


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def _version_check(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return {"command": " ".join(command), "available": False, "stdout_tail": "", "stderr_tail": ""}
    return {
        "command": " ".join(command),
        "available": result.returncode == 0,
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }


def _value_hypothesis(name: str, item: dict[str, Any]) -> str:
    family = item.get("output_value_family") or "product_quality"
    return f"{name} may improve {family} if a direct product benchmark shows measurable lift."


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Free External Candidate Benchmark Report",
        "",
        f"Status: {report['status']}",
        "",
        "| Candidate | Status | Decision |",
        "|---|---|---|",
    ]
    for probe in report.get("probes", []):
        lines.append(f"| {probe['name']} | {probe['status']} | {probe['decision']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe free external benchmark candidates.")
    parser.add_argument(
        "--review-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "free_external_candidate_review.json"
    )
    parser.add_argument(
        "--report-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "free_external_candidate_benchmark_report.json"
    )
    parser.add_argument(
        "--markdown-path", type=Path, default=DEFAULT_EVIDENCE_DIR / "free_external_candidate_benchmark_report.md"
    )
    args = parser.parse_args()
    report = build_probe_report(args.review_path)
    write_json(args.report_path, report)
    write_markdown_report(args.markdown_path, report)
    print(
        "Free external probes: "
        f"eligible={report['summary']['eligible_candidate_count']} "
        f"ready={report['summary']['ready_for_product_benchmark_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
