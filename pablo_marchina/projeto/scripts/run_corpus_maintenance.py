#!/usr/bin/env python3
"""Run the controlled NVIDIA corpus maintenance sequence.

The sequence is intentionally conservative:
- source sync dry-run validates the allowlist before any fetching;
- freshness audit can fail on stale/expired content;
- Qdrant ingest dry-run validates/chunks without connecting to Qdrant;
- real Qdrant ingestion only runs when explicitly enabled.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORTS_ROOT = PROJECT_ROOT / "reports" / "corpus-maintenance"


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    started_at: str
    finished_at: str
    stdout_log: str
    stderr_log: str
    report_path: str | None = None
    required: bool = True


@dataclass
class MaintenanceSummary:
    maintenance_run_id: str
    started_at: str
    finished_at: str = ""
    run_sync: bool = True
    run_ingestion: bool = False
    run_evals: bool = True
    promote_sources: bool = False
    recreate_collection: bool = False
    fail_on_stale: bool = False
    fail_on_expired: bool = True
    reports_dir: str = ""
    steps: list[StepResult] = field(default_factory=list)

    @property
    def failed_required_steps(self) -> list[StepResult]:
        return [step for step in self.steps if step.required and step.returncode != 0]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run controlled NVIDIA corpus maintenance.",
    )
    parser.add_argument(
        "--run-sync",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run source sync dry-run. Default: true.",
    )
    parser.add_argument(
        "--run-ingestion",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run real Qdrant ingestion after the dry-run. Default: false.",
    )
    parser.add_argument(
        "--run-evals",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run RAG and golden evals. Default: true.",
    )
    parser.add_argument(
        "--promote-sources",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run source sync with --promote after the dry-run. Default: false.",
    )
    parser.add_argument(
        "--recreate-collection",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Pass --recreate-collection to real ingestion. Default: false.",
    )
    parser.add_argument(
        "--fail-on-stale",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fail freshness audit when stale sources exist. Default: false.",
    )
    parser.add_argument(
        "--fail-on-expired",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail freshness audit when expired sources exist. Default: true.",
    )
    parser.add_argument(
        "--reports-dir",
        default=None,
        help="Directory for reports. Default: reports/corpus-maintenance/<run-id>.",
    )
    parser.add_argument(
        "--collection-name",
        default="nvidia_corpus",
        help="Qdrant collection name for ingestion. Default: nvidia_corpus.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = f"maintenance_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    reports_dir = Path(args.reports_dir) if args.reports_dir else DEFAULT_REPORTS_ROOT / run_id
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary = MaintenanceSummary(
        maintenance_run_id=run_id,
        started_at=datetime.now(UTC).isoformat(),
        run_sync=args.run_sync,
        run_ingestion=args.run_ingestion,
        run_evals=args.run_evals,
        promote_sources=args.promote_sources,
        recreate_collection=args.recreate_collection,
        fail_on_stale=args.fail_on_stale,
        fail_on_expired=args.fail_on_expired,
        reports_dir=str(reports_dir),
    )

    print("NVIDIA Corpus Maintenance")
    print(f"  Run ID:      {run_id}")
    print(f"  Reports dir: {reports_dir}")
    print(f"  Real ingest: {args.run_ingestion}")
    print(f"  Promote:     {args.promote_sources}")
    print()

    try:
        if args.run_sync:
            run_required_step(
                summary,
                "source_sync_dry_run",
                [
                    sys.executable,
                    "scripts/sync_nvidia_sources.py",
                    "--dry-run",
                    "--fail-on-validation-error",
                    "--report-path",
                    str(reports_dir / "source_sync_dry_run.json"),
                ],
                reports_dir,
                report_path=reports_dir / "source_sync_dry_run.json",
            )
            if args.promote_sources:
                run_required_step(
                    summary,
                    "source_sync_promote",
                    [
                        sys.executable,
                        "scripts/sync_nvidia_sources.py",
                        "--promote",
                        "--report-path",
                        str(reports_dir / "source_sync_promote.json"),
                    ],
                    reports_dir,
                    report_path=reports_dir / "source_sync_promote.json",
                )

        audit_cmd = [
            sys.executable,
            "scripts/audit_nvidia_corpus_freshness.py",
            "--format",
            "json",
            "--report-path",
            str(reports_dir / "freshness_audit.json"),
        ]
        if args.fail_on_stale:
            audit_cmd.append("--fail-on-stale")
        if args.fail_on_expired:
            audit_cmd.append("--fail-on-expired")
        run_required_step(
            summary,
            "freshness_audit",
            audit_cmd,
            reports_dir,
            report_path=reports_dir / "freshness_audit.json",
        )

        run_required_step(
            summary,
            "qdrant_ingest_dry_run",
            [
                sys.executable,
                "scripts/ingest_nvidia_corpus.py",
                "--dry-run",
                "--mock-embeddings",
                "--report-path",
                str(reports_dir / "qdrant_ingest_dry_run.json"),
            ],
            reports_dir,
            report_path=reports_dir / "qdrant_ingest_dry_run.json",
        )

        if args.run_ingestion:
            ingest_cmd = [
                sys.executable,
                "scripts/ingest_nvidia_corpus.py",
                "--collection-name",
                args.collection_name,
                "--report-path",
                str(reports_dir / "qdrant_ingestion.json"),
            ]
            if args.recreate_collection:
                ingest_cmd.append("--recreate-collection")
            run_required_step(
                summary,
                "qdrant_ingestion",
                ingest_cmd,
                reports_dir,
                report_path=reports_dir / "qdrant_ingestion.json",
            )

        if args.run_evals:
            run_required_step(
                summary,
                "rag_evals",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/unit/test_rag_eval.py",
                    "tests/unit/test_rag_eval_semantic.py",
                    "tests/unit/test_rag_eval_reranking.py",
                    "--tb=short",
                    "--junitxml",
                    str(reports_dir / "rag_eval_junit.xml"),
                ],
                reports_dir,
                report_path=reports_dir / "rag_eval_junit.xml",
            )
            run_required_step(
                summary,
                "golden_evals",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/evals/",
                    "--tb=short",
                    "--junitxml",
                    str(reports_dir / "golden_eval_junit.xml"),
                ],
                reports_dir,
                report_path=reports_dir / "golden_eval_junit.xml",
            )
            run_required_step(
                summary,
                "answer_quality_evals",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/evals/test_answer_quality_golden.py",
                    "--tb=short",
                    "--junitxml",
                    str(reports_dir / "answer_quality_eval_junit.xml"),
                ],
                reports_dir,
                report_path=reports_dir / "answer_quality_eval_junit.xml",
            )
    finally:
        summary.finished_at = datetime.now(UTC).isoformat()
        write_summary(summary, reports_dir / "maintenance_summary.json")

    failed = summary.failed_required_steps
    if failed:
        print("Maintenance failed:")
        for step in failed:
            print(f"  - {step.name}: exit {step.returncode}")
        return 1

    print("Maintenance completed successfully.")
    print(f"Summary: {reports_dir / 'maintenance_summary.json'}")
    return 0


def run_required_step(
    summary: MaintenanceSummary,
    name: str,
    command: list[str],
    reports_dir: Path,
    *,
    report_path: Path | None = None,
) -> None:
    result = run_step(name, command, reports_dir, report_path=report_path)
    summary.steps.append(result)
    write_summary(summary, reports_dir / "maintenance_summary.json")
    if result.returncode != 0:
        raise SystemExit(1)


def run_step(
    name: str,
    command: list[str],
    reports_dir: Path,
    *,
    report_path: Path | None = None,
) -> StepResult:
    started_at = datetime.now(UTC).isoformat()
    stdout_path = reports_dir / f"{name}.stdout.log"
    stderr_path = reports_dir / f"{name}.stderr.log"
    print(f"==> {name}")
    print("    " + " ".join(command))

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    finished_at = datetime.now(UTC).isoformat()

    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)
    print(f"<== {name}: exit {completed.returncode}")
    print()

    return StepResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        started_at=started_at,
        finished_at=finished_at,
        stdout_log=str(stdout_path),
        stderr_log=str(stderr_path),
        report_path=str(report_path) if report_path is not None else None,
    )


def write_summary(summary: MaintenanceSummary, path: Path) -> None:
    path.write_text(
        json.dumps(asdict(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
