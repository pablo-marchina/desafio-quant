#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LLM/RAG security tests and write final evidence reports.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    command = [sys.executable, "-m", "pytest", "tests/security", "-q"]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    missing_pytest = result.returncode != 0 and "No module named pytest" in (result.stderr + result.stdout)
    status = "PASS" if result.returncode == 0 else ("BLOCKED_BY_ENVIRONMENT" if missing_pytest else "FAIL")
    generated_at = datetime.now(UTC).isoformat()
    base_report = {
        "status": status,
        "report_id": "llm_security_suite_report",
        "generated_at": generated_at,
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
        "remediation": "Install dev dependencies with `pip install -e .[dev,security]`." if missing_pytest else "",
        "cases": [
            "direct_prompt_injection",
            "indirect_prompt_injection",
            "rag_poisoning",
            "tool_abuse",
            "data_exfiltration",
            "system_prompt_leakage",
            "malicious_source_content",
            "over_permissioned_agent",
            "output_validation",
        ],
    }
    write_json(args.evidence_dir / "llm_security_suite_report.json", base_report)
    write_json(
        args.evidence_dir / "prompt_injection_test_report.json",
        {
            **base_report,
            "report_id": "prompt_injection_test_report",
            "cases": ["direct_prompt_injection", "indirect_prompt_injection"],
        },
    )
    write_json(
        args.evidence_dir / "rag_poisoning_test_report.json",
        {**base_report, "report_id": "rag_poisoning_test_report", "cases": ["rag_poisoning"]},
    )
    write_json(
        args.evidence_dir / "tool_abuse_test_report.json",
        {**base_report, "report_id": "tool_abuse_test_report", "cases": ["tool_abuse", "secret_leakage"]},
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    print(f"LLM_SECURITY_SUITE_STATUS={status}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
