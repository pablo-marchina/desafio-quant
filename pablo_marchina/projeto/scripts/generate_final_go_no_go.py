#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final GO/NO-GO report from proof summary.")
    parser.add_argument("--evidence-dir", type=Path, default=Path("final_case_evidence"))
    args = parser.parse_args()
    summary_path = args.evidence_dir / "final_proof_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {"final_status": "FAIL", "results": [], "reason": "final_proof_summary.json missing"}
    mode = summary.get("mode")
    go = (
        mode == "full"
        and summary.get("final_status") == "PASS"
        and all(
            result.get("status") == "PASS" or not result.get("required", True)
            for result in summary.get("results", [])
            if isinstance(result, dict)
        )
    )
    nonpassing_gates = [
        result for result in summary.get("results", []) if isinstance(result, dict) and result.get("status") != "PASS"
    ]
    report = {
        "report_id": "final_product_go_no_go_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "GO" if go else "NO_GO",
        "final_status": summary.get("final_status", "FAIL"),
        "mode": mode or "unknown",
        "go_requires_full_proof": True,
        "all_critical_gates_passed": go,
        "blocking_gates": nonpassing_gates,
        "critical_blocking_gates": [result for result in nonpassing_gates if result.get("required", True)],
        "environment_blockers": [
            result for result in nonpassing_gates if result.get("status") == "BLOCKED_BY_ENVIRONMENT"
        ],
    }
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    (args.evidence_dir / "final_product_go_no_go_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.evidence_dir / "final_product_go_no_go_report.md").write_text(
        "\n".join(
            [
                "# Final Product Go/No-Go Report",
                "",
                f"Status: `{report['status']}`",
                f"All critical gates passed: `{report['all_critical_gates_passed']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.evidence_dir / "final_acceptance_manifest.json").write_text(
        json.dumps({"status": report["status"], "source": "generate_final_go_no_go.py"}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"FINAL_PRODUCT_GO_NO_GO={report['status']}")
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())
