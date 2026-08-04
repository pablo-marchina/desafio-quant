#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json


def _pytest_command(*args: str) -> list[str]:
    pytest_executable = shutil.which("pytest")
    if pytest_executable:
        return [pytest_executable, *args]
    return [sys.executable, "-m", "pytest", *args]


def _run(command: list[str], *, required: bool, timeout_seconds: int = 180) -> dict[str, Any]:
    label = " ".join(command)
    try:
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT) + (__import__("os").pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "label": label,
            "returncode": None,
            "required": required,
            "status": "FAIL" if required else "BLOCKED_BY_ENVIRONMENT",
            "stdout_tail": "",
            "stderr_tail": f"Timed out after {exc.timeout} seconds.",
        }
    status = "PASS" if result.returncode == 0 else ("FAIL" if required else "WARN")
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return {
        "label": label,
        "returncode": result.returncode,
        "required": required,
        "status": status,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final product proof gates.")
    parser.add_argument("--quick", action="store_true", help="Skip expensive full test/build commands.")
    parser.add_argument(
        "--local-proof-only",
        action="store_true",
        help="Run only local deterministic proof gates that do not require live services or scanners.",
    )
    parser.add_argument("--full", action="store_true", help="Explicit full mode; default when --quick is not set.")
    parser.add_argument("--skip-live", action="store_true", help="Skip live collection.")
    parser.add_argument("--skip-doctor", action="store_true", help="Skip local proof doctor before real services.")
    parser.add_argument(
        "--require-docker-compose", action="store_true", help="Require Docker Compose even if services exist."
    )
    parser.add_argument("--external-services-ok", dest="external_services_ok", action="store_true")
    parser.add_argument("--no-external-services-ok", dest="external_services_ok", action="store_false")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.set_defaults(external_services_ok=True)
    args = parser.parse_args()

    evidence_dir_arg = str(args.evidence_dir)
    local_proof_commands: list[tuple[list[str], bool]] = [
        ([sys.executable, "scripts/check_single_runtime_pipeline.py"], True),
        ([sys.executable, "scripts/check_no_mock_runtime.py"], True),
        (
            [
                sys.executable,
                "scripts/build_runtime_usage_inventory.py",
                "--output",
                str(args.evidence_dir / "runtime_usage_inventory.csv"),
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/build_best_case_runtime_report.py",
                "--inventory",
                str(args.evidence_dir / "runtime_usage_inventory.csv"),
                "--output",
                str(args.evidence_dir / "best_case_runtime_report.json"),
            ],
            True,
        ),
        (
            _pytest_command(
                "tests/unit/test_best_case_runtime_report.py",
                "tests/unit/test_runtime_usage_inventory.py",
                "tests/unit/test_ai_native_model.py",
                "--tb=short",
            ),
            True,
        ),
    ]
    commands: list[tuple[list[str], bool]] = local_proof_commands if args.local_proof_only else [
        ([sys.executable, "scripts/check_referenced_scripts_exist.py"], True),
        ([sys.executable, "scripts/check_source_repo_clean.py"], True),
        ([sys.executable, "scripts/generate_final_evidence_pack.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/generate_finalization_evidence.py", "--evidence-dir", evidence_dir_arg], True),
        (
            [
                sys.executable,
                "scripts/check_product_configuration.py",
                "--actual-env-only",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        ([sys.executable, "scripts/check_no_mock_runtime.py"], True),
        ([sys.executable, "scripts/check_no_method_only_runtime_modules.py"], True),
        ([sys.executable, "scripts/run_llm_security_suite.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/run_secret_scan.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/run_dependency_scan.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/run_sast_scan.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/generate_sbom.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/run_container_scan.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/run_openssf_scorecard.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_free_external_tools.py"], True),
        ([sys.executable, "scripts/check_api_key_readiness.py"], True),
        ([sys.executable, "scripts/build_candidate_decision_matrix.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_candidate_promotion_closure.py", "--evidence-dir", evidence_dir_arg], True),
        (
            [
                sys.executable,
                "scripts/run_benchmark.py",
                "--suite",
                "complete-catalog",
                "--candidate-catalog",
                str(args.evidence_dir / "candidate_catalog.csv"),
                "--results-path",
                str(args.evidence_dir / "benchmark_results.jsonl"),
                "--report-path",
                str(args.evidence_dir / "benchmark_report.json"),
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/check_candidate_catalog.py",
                "--catalog",
                str(args.evidence_dir / "candidate_catalog.csv"),
                "--require-benchmark-coverage",
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/check_external_free_verification.py",
                "--catalog",
                str(args.evidence_dir / "candidate_catalog.csv"),
                "--report-path",
                str(args.evidence_dir / "external_free_verification_report.json"),
                "--markdown-path",
                str(args.evidence_dir / "external_free_verification_report.md"),
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/review_free_external_candidates.py",
                "--catalog",
                str(args.evidence_dir / "candidate_catalog.csv"),
                "--report-path",
                str(args.evidence_dir / "free_external_candidate_review.json"),
                "--markdown-path",
                str(args.evidence_dir / "free_external_candidate_review.md"),
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/rank_value_candidates.py",
                "--catalog",
                str(args.evidence_dir / "candidate_catalog.csv"),
                "--free-external-review",
                str(args.evidence_dir / "free_external_candidate_review.json"),
                "--queue-path",
                str(args.evidence_dir / "ranked_value_candidate_queue.json"),
                "--markdown-path",
                str(args.evidence_dir / "ranked_value_candidate_queue.md"),
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_free_external_candidate_benchmarks.py",
                "--review-path",
                str(args.evidence_dir / "free_external_candidate_review.json"),
                "--report-path",
                str(args.evidence_dir / "free_external_candidate_benchmark_report.json"),
                "--markdown-path",
                str(args.evidence_dir / "free_external_candidate_benchmark_report.md"),
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_ranked_value_benchmarks.py",
                "--catalog",
                str(args.evidence_dir / "candidate_catalog.csv"),
                "--queue-path",
                str(args.evidence_dir / "ranked_value_candidate_queue.json"),
                "--report-path",
                str(args.evidence_dir / "ranked_value_benchmark_report.json"),
                "--markdown-path",
                str(args.evidence_dir / "ranked_value_benchmark_report.md"),
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_diagnostic_value_triage.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_family_spike_benchmarks.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_query_rewriting_product_spike.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_next_action_enrichment_product_spike.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_graphrag_evidence_graph_product_spike.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_counter_evidence_product_spike.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_source_quality_product_spike.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        (
            [
                sys.executable,
                "scripts/run_evidence_sufficiency_product_spike.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        ([sys.executable, "scripts/check_implemented_family_best_tool.py", "--evidence-dir", evidence_dir_arg], True),
        (
            [
                sys.executable,
                "scripts/run_direct_alternative_gap_benchmarks.py",
                "--evidence-dir",
                evidence_dir_arg,
            ],
            True,
        ),
        ([sys.executable, "scripts/check_implemented_family_best_tool.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_value_family_completeness.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_roadmap_closure_audit.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_repository_clean.py"], True),
        ([sys.executable, "scripts/package_final_release.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_final_release_zip.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_benchmark_type_policy.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_runtime_value_policy.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_numeric_governance.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_source_compliance.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_lineage_coverage.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_security_release.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_finalization_governance.py", "--evidence-dir", evidence_dir_arg], True),
        ([sys.executable, "scripts/check_no_demo_dependency.py"], True),
    ]
    if not args.skip_live and not args.local_proof_only:
        commands.insert(
            1, ([sys.executable, "scripts/live_collect.py", "--live", "--evidence-dir", evidence_dir_arg], True)
        )
    real_service_command: list[str] | None = None
    if not args.quick and not args.local_proof_only:
        commands.extend(
            [
                (
                    _pytest_command(
                        "tests/unit/test_governance_schemas.py",
                        "tests/unit/test_governance_artifacts.py",
                        "tests/unit/test_benchmark_runner.py",
                        "tests/unit/test_final_gate_scripts.py",
                        "tests/unit/test_real_service_proof.py",
                        "tests/unit/test_local_proof_doctor.py",
                        "tests/unit/test_full_proof_pass_attempt.py",
                        "tests/unit/test_ingest_nvidia_corpus.py",
                        "tests/unit/test_product_acceptance_script.py",
                        "--basetemp",
                        ".pytest_tmp_final",
                        "--tb=short",
                    ),
                    True,
                ),
            ]
        )
        if not args.skip_doctor:
            doctor_command = [
                sys.executable,
                "scripts/local_proof_doctor.py",
                "--evidence-dir",
                evidence_dir_arg,
            ]
            if args.require_docker_compose:
                doctor_command.append("--require-docker-compose")
            if not args.external_services_ok:
                doctor_command.append("--no-external-services-ok")
            commands.append((doctor_command, False))
        real_service_command = [
            sys.executable,
            "scripts/real_service_proof.py",
            "--product-like-acceptance",
            "--auto-start-services",
            "--ingest-corpus",
            "--reset-qdrant",
            "--evidence-dir",
            evidence_dir_arg,
        ]
        if args.require_docker_compose:
            real_service_command.append("--require-docker-compose")

    results: list[dict[str, Any]] = []
    doctor_status = "SKIPPED" if args.skip_doctor or args.quick else "NOT_RUN"
    for command, required in commands:
        timeout_seconds = 420 if "scripts/real_service_proof.py" in command else 180
        result = _run(command, required=required, timeout_seconds=timeout_seconds)
        if "scripts/local_proof_doctor.py" in result["label"]:
            result = _enrich_doctor_status(result, args.evidence_dir)
            doctor_status = result["status"]
        if "scripts/real_service_proof.py" in result["label"]:
            result = _enrich_real_service_status(result, args.evidence_dir)
        results.append(result)

    if real_service_command is not None:
        if doctor_status in {"PASS", "SKIPPED"}:
            result = _run(real_service_command, required=False, timeout_seconds=420)
            result = _enrich_real_service_status(result, args.evidence_dir)
            results.append(result)
        else:
            results.append(_skipped_real_service_result(doctor_status, args.evidence_dir))

    failures = [result for result in results if result["status"] == "FAIL"]
    warnings = [result for result in results if result["status"] == "WARN"]
    blocked = [result for result in results if result["status"] == "BLOCKED_BY_ENVIRONMENT"]
    final_status = "FAIL" if failures else ("BLOCKED_BY_ENVIRONMENT" if blocked else "PASS")
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "local_proof_only" if args.local_proof_only else ("quick" if args.quick else "full"),
        "final_status": final_status,
        "total_gates": len(results),
        "passed": sum(1 for result in results if result["status"] == "PASS"),
        "failed": len(failures),
        "warnings": len(warnings),
        "blocked_by_environment": len(blocked),
        "results": results,
    }
    _attach_doctor_reference(summary, args.evidence_dir)
    _write_readiness_reports(args.evidence_dir, summary)
    if failures:
        print("FINAL_PRODUCT_STATUS=FAIL")
        for result in failures:
            print(f"  failed({result['returncode']}): {result['label']}")
        return 1
    if blocked:
        print("FINAL_PRODUCT_STATUS=BLOCKED_BY_ENVIRONMENT")
        for result in blocked:
            print(f"  blocked: {result['label']}")
        return 0

    print("FINAL_PRODUCT_STATUS=PASS")
    return 0


def _write_readiness_reports(evidence_dir: Path, summary: dict[str, Any]) -> None:
    write_json(evidence_dir / "final_proof_summary.json", summary)
    write_json(evidence_dir / "full_proof_run.json", summary)
    write_json(evidence_dir / "product_readiness_report.json", summary)
    go = summary["mode"] == "full" and summary["final_status"] == "PASS"
    go_no_go = {
        "report_id": "final_product_go_no_go_report",
        "status": "GO" if go else "NO_GO",
        "final_status": summary["final_status"],
        "generated_at": summary["generated_at"],
        "go_requires_full_proof": True,
        "total_gates": summary["total_gates"],
        "passed": summary["passed"],
        "failed": summary["failed"],
        "warnings": summary["warnings"],
        "blocked_by_environment": summary["blocked_by_environment"],
        "blocking_gates": [
            result for result in summary["results"] if result["status"] in {"FAIL", "BLOCKED_BY_ENVIRONMENT"}
        ],
    }
    write_json(evidence_dir / "final_product_go_no_go_report.json", go_no_go)
    _write_gate_projection(evidence_dir / "no_demo_report.json", summary, "scripts/check_no_demo_dependency.py")
    _write_gate_projection(evidence_dir / "repository_clean_report.json", summary, "scripts/check_repository_clean.py")
    _write_full_proof_junit(evidence_dir / "full_proof_junit.xml", summary)
    lines = [
        "# Product Readiness Report",
        "",
        f"Generated at: `{summary['generated_at']}`",
        f"Mode: {summary['mode']}",
        f"Final status: {summary['final_status']}",
        "",
        "| Gate | Status | Return code |",
        "|---|---:|---:|",
    ]
    for result in summary["results"]:
        lines.append(f"| `{result['label']}` | {result['status']} | {result['returncode']} |")
    lines.append("")
    (evidence_dir / "product_readiness_report.md").write_text("\n".join(lines), encoding="utf-8")
    _write_go_no_go_markdown(evidence_dir / "final_product_go_no_go_report.md", go_no_go)
    _write_runtime_bom_final(evidence_dir)


def _write_go_no_go_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Final Product Go/No-Go Report",
        "",
        f"Status: `{report['status']}`",
        f"Final proof status: `{report['final_status']}`",
        f"Generated at: `{report['generated_at']}`",
        "",
        "| Gate | Status | Return code |",
        "|---|---:|---:|",
    ]
    for result in report["blocking_gates"]:
        lines.append(f"| `{result['label']}` | {result['status']} | {result['returncode']} |")
    if not report["blocking_gates"]:
        lines.append("| All gates | PASS | 0 |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_runtime_bom_final(evidence_dir: Path) -> None:
    source = evidence_dir / "runtime_bom.json"
    target = evidence_dir / "runtime_bom_final.json"
    if source.exists():
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _write_full_proof_junit(path: Path, summary: dict[str, Any]) -> None:
    failures = [result for result in summary["results"] if result["status"] == "FAIL"]
    blocked = [result for result in summary["results"] if result["status"] == "BLOCKED_BY_ENVIRONMENT"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<testsuite name="final-product-proof" tests="{len(summary["results"])}" '
            f'failures="{len(failures)}" errors="0" skipped="{len(blocked)}">'
        ),
    ]
    for result in summary["results"]:
        name = _xml_escape(result["label"])
        status = result["status"]
        lines.append(f'  <testcase classname="final_product" name="{name}">')
        if status == "FAIL":
            message = _xml_escape(result.get("stderr_tail") or result.get("stdout_tail") or "gate failed")
            lines.append(f'    <failure message="{message}" />')
        elif status == "BLOCKED_BY_ENVIRONMENT":
            message = _xml_escape(result.get("stderr_tail") or "blocked by environment")
            lines.append(f'    <skipped message="{message}" />')
        lines.append("  </testcase>")
    lines.append("</testsuite>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _xml_escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _attach_doctor_reference(summary: dict[str, Any], evidence_dir: Path) -> None:
    report_path = evidence_dir / "local_proof_doctor_report.json"
    if summary.get("final_status") != "BLOCKED_BY_ENVIRONMENT" or not report_path.exists():
        return
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    summary["environment_doctor"] = {
        "report_path": str(report_path),
        "status": payload.get("status"),
        "effective_service_route": payload.get("effective_service_route"),
        "recommended_route": payload.get("recommended_route"),
        "exact_commands": payload.get("exact_commands", []),
        "human_summary": payload.get("human_summary", ""),
        "can_retry_without_code_changes": payload.get("can_retry_without_code_changes"),
    }


def _enrich_real_service_status(result: dict[str, Any], evidence_dir: Path) -> dict[str, Any]:
    report_path = evidence_dir / "real_service_proof_report.json"
    if not report_path.exists():
        return result
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if payload.get("status") == "BLOCKED_BY_ENVIRONMENT":
        result["status"] = "BLOCKED_BY_ENVIRONMENT"
    elif payload.get("status") == "FAIL":
        result["status"] = "FAIL"
        result["returncode"] = 1
    return result


def _enrich_doctor_status(result: dict[str, Any], evidence_dir: Path) -> dict[str, Any]:
    report_path = evidence_dir / "local_proof_doctor_report.json"
    if not report_path.exists():
        return result
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    status = payload.get("status")
    if status in {"PASS", "WARN", "FAIL", "BLOCKED_BY_ENVIRONMENT"}:
        result["status"] = status
    if status == "FAIL":
        result["returncode"] = 1
    result["effective_service_route"] = payload.get("effective_service_route")
    result["blocking_checks"] = [
        check.get("check_id") for check in payload.get("blocking_checks", []) if isinstance(check, dict)
    ]
    return result


def _skipped_real_service_result(doctor_status: str, evidence_dir: Path) -> dict[str, Any]:
    report_path = evidence_dir / "local_proof_doctor_report.json"
    blockers: list[str] = []
    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        blockers = [check.get("check_id", "unknown") for check in payload.get("blocking_checks", [])]
    status = "FAIL" if doctor_status == "FAIL" else "BLOCKED_BY_ENVIRONMENT"
    write_json(
        evidence_dir / "real_service_proof_report.json",
        {
            "report_id": "real_service_proof_report",
            "status": status,
            "generated_at": datetime.now(UTC).isoformat(),
            "skipped_by": "local_proof_doctor",
            "doctor_status": doctor_status,
            "doctor_report": str(report_path),
            "blocking_checks": blockers,
            "reports": [],
            "settings": {},
        },
    )
    return {
        "label": "scripts/real_service_proof.py (skipped by local proof doctor)",
        "returncode": 0,
        "required": False,
        "status": status,
        "stdout_tail": "",
        "stderr_tail": f"Skipped because local proof doctor status is {doctor_status}. Blocking checks: {blockers}",
    }


def _write_gate_projection(path: Path, summary: dict[str, Any], label_fragment: str) -> None:
    matches = [result for result in summary["results"] if label_fragment in result["label"]]
    if not matches:
        write_json(
            path,
            {
                "status": "WARN",
                "reason": f"Gate not executed: {label_fragment}",
                "final_proof_ref": "final_case_evidence/final_proof_summary.json",
            },
        )
        return
    result = matches[-1]
    write_json(
        path,
        {
            "status": result["status"],
            "returncode": result["returncode"],
            "label": result["label"],
            "stdout_tail": result["stdout_tail"],
            "stderr_tail": result["stderr_tail"],
            "final_proof_ref": "final_case_evidence/final_proof_summary.json",
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
