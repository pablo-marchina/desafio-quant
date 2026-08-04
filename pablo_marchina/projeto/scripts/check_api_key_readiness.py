#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = PROJECT_ROOT / "data" / "free_external_tool_registry.csv"
DEFAULT_REPORT = PROJECT_ROOT / "final_case_evidence" / "api_key_readiness_report.json"

ENV_BY_TOOL = {
    "OpenAI Evals": "OPENAI_API_KEY",
    "LangSmith": "LANGSMITH_API_KEY",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check readiness for configured free external API tools.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    checks: list[dict[str, object]] = []
    failures: list[str] = []
    if args.registry.exists():
        with args.registry.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("api_key_required", "").lower() != "true":
                    continue
                env_key = ENV_BY_TOOL.get(row["tool"], f"{row['provider'].upper().replace(' ', '_')}_API_KEY")
                configured = row.get("configured", "").lower() == "true"
                is_set = bool(os.environ.get(env_key, "").strip())
                status = "PASS" if not configured or is_set else "FAIL"
                if status == "FAIL":
                    failures.append(f"{row['tool']} is configured but {env_key} is missing")
                checks.append(
                    {
                        "tool": row["tool"],
                        "env_key": env_key,
                        "configured": configured,
                        "is_set": is_set,
                        "status": status,
                    }
                )
    else:
        failures.append(f"missing registry: {args.registry}")

    payload = {
        "report_id": "api_key_readiness_report",
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": checks,
        "failures": failures,
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        print("FAIL: API key readiness")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: API key readiness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
