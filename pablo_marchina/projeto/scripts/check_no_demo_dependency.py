#!/usr/bin/env python3
"""
Check that the product flow does not depend on demo routes, demo data, or
sample-first UI paths.

This script verifies:
1. No reference to demo artifacts in src/ or frontend/src/ product code
2. No import or read of demo data in the product pipeline
3. No automatic fallback to demo data

Allowed exceptions (documented and justified):
- tests/fixtures/ -- test fixtures are allowed
- docs/ -- documentation may reference demo data
- examples/golden, examples/rag_eval, examples/answer_quality -- evaluation fixtures
- Lines containing "# no-demo-dependency-check-ignore" are excluded

Exit codes:
- 0: no violations found
- 1: violations found (blocking)
- 2: error during check
"""

import os
import re
import sys

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

SCAN_PATHS = ["src", os.path.join("frontend", "src")]

FORBIDDEN_PATTERNS = {
    "data/demo_runs": re.compile(r"data[\\/]demo_runs"),
    "examples/demo": re.compile(r"examples[\\/]demo"),
    "sample_inputs": re.compile(r"sample_inputs"),
    "sampleStartupInput": re.compile(r"sampleStartupInput"),
    "demo route": re.compile(r"['\"]/(?:demo|brief)(?:/|['\"]|\?)"),
}

# Lines matching these patterns assert NO dependency (acceptable, not a violation)
ASSERTION_PATTERNS = [
    re.compile(r"(do|does|will|shall)\s+not\s+(access|use|read|depend|rely)", re.IGNORECASE),
    re.compile(r"never\s+access", re.IGNORECASE),
    re.compile(r"no\s+(access|dependency|reference)", re.IGNORECASE),
    re.compile(r"#\s*no-demo-dependency"),
]

ALLOWED_PREFIXES = (
    "docs/",
    "tests/fixtures/",
    "tests/acceptance/",
    os.path.join("scripts", "check_no_demo_dependency.py"),
)


def is_allowed(filepath: str) -> bool:
    normalized = filepath.replace("\\", "/")
    return any(normalized.startswith(p) for p in ALLOWED_PREFIXES)


def scan_file(filepath: str) -> list[str]:
    violations = []
    if is_allowed(filepath):
        return violations
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                matched = [label for label, pattern in FORBIDDEN_PATTERNS.items() if pattern.search(line)]
                if matched:
                    is_assertion = any(p.search(line) for p in ASSERTION_PATTERNS)
                    if is_assertion:
                        continue

                    violations.append(
                        f"  {filepath}:{i}: references forbidden demo surface(s): " f"{', '.join(matched)}"
                    )
    except Exception as e:
        violations.append(f"  {filepath}: ERROR reading file: {e}")
    return violations


def main() -> int:
    violations = []
    for scan_path in SCAN_PATHS:
        abs_path = os.path.join(REPO_ROOT, scan_path)
        if not os.path.exists(abs_path):
            print(f"[WARN] Scan path not found: {scan_path}")
            continue
        for root, dirs, files in os.walk(abs_path):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules")]
            for filename in files:
                if not filename.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".md")):
                    continue
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, REPO_ROOT)
                violations.extend(scan_file(rel_path))

    if violations:
        print("=" * 60)
        print("NO DEMO DEPENDENCY CHECK - V I O L A T I O N S  F O U N D")
        print("=" * 60)
        for v in violations:
            print(v)
        print("-" * 60)
        print(f"Total violations: {len(violations)}")
        print("FAIL: Product code references forbidden demo routes or demo data.")
        print("=" * 60)
        return 1
    else:
        print("=" * 60)
        print("NO DEMO DEPENDENCY CHECK - P A S S E D")
        print("=" * 60)
        print(f"Scanned: {SCAN_PATHS}")
        print("Result: No forbidden demo references found.")
        print("The product flow uses DB/API real, not demo data.")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
