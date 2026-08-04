"""CI evaluation runner for deterministic offline quality suites.

Usage::

    python -m src.evaluation.eval_runner                  # run required suites
    python -m src.evaluation.eval_runner --suite rag      # single suite
    python -m src.evaluation.eval_runner --ci             # fail on regressions/config errors

Optional suites are reported as skipped when their test implementation is not
present. Required suites always fail fast on stale paths so CI cannot silently
claim coverage it does not execute.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.evaluation.result_store import BenchmarkResult, BenchmarkResultStore, MetricResult

_RESULTS_DIR = Path("data/eval_results")
_RESULTS_PATH = _RESULTS_DIR / "ci_results.jsonl"


@dataclass(frozen=True)
class SuiteDefinition:
    description: str
    pytest_args: tuple[str, ...]
    optional: bool = False


def _register_suite(name: str, description: str, pytest_args: list[str]) -> None:
    SUITES[name] = {"description": description, "pytest_args": pytest_args}


_register_suite(
    "rag",
    "RAG retrieval metrics, corpus governance, precision, and recall",
    [
        "tests/unit/test_corpus_release_contract.py",
        "tests/unit/test_rag_retrieval_contract.py",
        "tests/unit/test_rag_eval.py",
        "tests/unit/test_rag_eval_semantic.py",
        "tests/unit/test_rag_eval_reranking.py",
        "tests/evals/test_qdrant_retrieval_eval.py",
    ],
)
_register_suite(
    "answer_quality",
    "Answer quality evaluation via deterministic golden set",
    ["tests/evals/test_answer_quality_golden.py"],
)
_register_suite(
    "gap_diagnosis",
    "Gap diagnosis baseline accuracy",
    ["tests/evals/test_gap_diagnosis_baseline.py"],
)
_register_suite(
    "scraping",
    "Scraping baseline extraction quality",
    ["tests/evals/test_scraping_baseline.py"],
)
_register_suite(
    "source_evidence",
    "Source quality and evidence confidence calibration",
    ["tests/evals/test_source_evidence_baseline.py"],
)
_register_suite(
    "recommendation",
    "Recommendation engine calibration",
    ["tests/evals/test_recommendation_baseline.py"],
)
_register_suite(
    "ragas",
    "RAGAS evaluation metrics",
    ["tests/evals/test_ragas_eval.py"],
)


def _missing_suite_paths(pytest_args: list[str]) -> list[str]:
    return [path for path in pytest_args if path.endswith(".py") and not Path(path).is_file()]


def run_suite(name: str, store: BenchmarkResultStore, ci_mode: bool = False) -> bool:
    suite = SUITES.get(name)
    if suite is None:
        print(f"  UNKNOWN SUITE: {name}")
        return False

    print(f"\n{'=' * 60}")
    print(f"Suite: {name} — {suite['description']}")
    print(f"{'=' * 60}")

    missing_paths = _missing_suite_paths(suite["pytest_args"])
    if missing_paths:
        message = f"suite registry references missing test files: {', '.join(missing_paths)}"
        print(message)
        store.append(
            BenchmarkResult(
                run_id=f"{name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
                candidate_id=name,
                candidate_name=name,
                dataset_id="pytest",
                status="failed",
                error=message,
            )
        )
        return not ci_mode

    run_id = f"{name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    missing = _missing_paths(suite)
    if missing:
        missing_text = ", ".join(missing)
        if suite.optional:
            print(f"  Status: SKIPPED — optional test implementation missing: {missing_text}")
            _append_result(
                store,
                run_id=run_id,
                name=name,
                status="skipped",
                metadata={"missing_paths": missing, "optional": True},
            )
            return True

        error = f"Required suite references missing test files: {missing_text}"
        print(f"  Status: MISCONFIGURED — {error}")
        _append_result(
            store,
            run_id=run_id,
            name=name,
            status="failed",
            exit_code=4,
            error=error,
            metadata={"missing_paths": missing, "optional": False},
        )
        return not ci_mode

    pytest_args = [*suite.pytest_args, "--tb=short", "-q"]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *pytest_args],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        passed = result.returncode == 0
        status = "passed" if passed else "failed"

        # A failing evaluation must preserve the complete diagnostic output so
        # CI failures are actionable. Successful suites remain compact.
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        print(stdout[-1000:] if passed else stdout)
        if stderr:
            print(stderr[-1000:] if passed else stderr)

        store.append(
            BenchmarkResult(
                run_id=run_id,
                candidate_id=name,
                candidate_name=name,
                dataset_id="pytest",
                status=status,
                metrics=[
                    MetricResult(
                        name="exit_code",
                        value=result.returncode,
                        unit="code",
                        higher_is_better=result.returncode == 0,
                    )
                ],
                metadata={"stdout_len": len(stdout), "stderr_len": len(stderr)},
            )
        )
        print(f"  Status: {status.upper()} (exit code {result.returncode})")
        if ci_mode and not passed:
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  TIMEOUT after 600s")
        store.append(
            BenchmarkResult(
                run_id=run_id,
                candidate_id=name,
                candidate_name=name,
                dataset_id="pytest",
                status="failed",
                error="Timeout (600s)",
            )
        )
        return not ci_mode
    except Exception as exc:
        print(f"  FAILED: {exc}")
        store.append(
            BenchmarkResult(
                run_id=run_id,
                candidate_id=name,
                candidate_name=name,
                dataset_id="pytest",
                status="failed",
                error=str(exc),
            )
        )
        return not ci_mode


def main() -> None:
    parser = argparse.ArgumentParser(description="CI eval runner")
    parser.add_argument("--suite", choices=list(SUITES.keys()) + ["all"], default="all")
    parser.add_argument("--ci", action="store_true", help="Fail when any suite regresses")
    args = parser.parse_args()

    store = BenchmarkResultStore(_RESULTS_PATH)
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    suites_to_run = list(SUITES) if args.suite == "all" else [args.suite]
    all_passed = True

    for name in suites_to_run:
        if not run_suite(name, store, ci_mode=args.ci):
            all_passed = False

    print(f"\n{'=' * 60}")
    print(f"Results saved to: {_RESULTS_PATH}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
