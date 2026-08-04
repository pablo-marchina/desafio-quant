#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

REQUIRED_COLUMNS = {"candidate_id", "name", "category"}


def validate_candidate_catalog(path: Path, *, require_benchmark_coverage: bool = False) -> list[str]:
    failures: list[str] = []
    if not path.exists():
        return [f"Missing candidate catalog: {path}"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            failures.append(f"Missing required columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        failures.append("Candidate catalog is empty.")
    ids = [row.get("candidate_id", "").strip() for row in rows]
    duplicates = sorted({item for item in ids if item and ids.count(item) > 1})
    if duplicates:
        failures.append(f"Duplicate candidate_id values: {', '.join(duplicates)}")
    if require_benchmark_coverage and "benchmark" in columns:
        uncovered = [
            row.get("candidate_id", "")
            for row in rows
            if row.get("status", "").upper() in {"BENCHMARKED", "BENCHMARK_CONFIGURED"}
            and not row.get("benchmark", "").strip()
        ]
        if uncovered:
            failures.append(f"Benchmarked candidates without benchmark path: {', '.join(uncovered[:10])}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate candidate catalog structure.")
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--require-benchmark-coverage", action="store_true")
    args = parser.parse_args()

    failures = validate_candidate_catalog(args.catalog, require_benchmark_coverage=args.require_benchmark_coverage)
    if failures:
        print("FAIL: candidate catalog")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: candidate catalog")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
