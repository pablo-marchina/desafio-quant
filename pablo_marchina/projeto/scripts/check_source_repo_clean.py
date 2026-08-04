#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_TRACKED_PATTERNS = (
    ".env",
    "frontend/node_modules/",
    "frontend/dist/",
    ".pytest_cache/",
    ".ruff_cache/",
    "__pycache__/",
    ".pyc",
    ".tsbuildinfo",
    "data/product/",
    "release/",
)


def validate_source_repo_clean() -> list[str]:
    failures: list[str] = []
    tracked = _git_ls_files()
    for path in tracked:
        normalized = path.replace("\\", "/")
        if _forbidden(normalized):
            failures.append(f"tracked forbidden artifact: {normalized}")
    return failures


def _git_ls_files() -> list[str]:
    result = subprocess.run(["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _forbidden(path: str) -> bool:
    if path.endswith(".env.example") or ".env." in path and path.endswith(".example"):
        return False
    return any(pattern in path or path == pattern for pattern in FORBIDDEN_TRACKED_PATTERNS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate source repository cleanliness.")
    parser.parse_args()
    failures = validate_source_repo_clean()
    if failures:
        print("FAIL: source repo clean")
        for failure in failures[:100]:
            print(f"  {failure}")
        return 1
    print("PASS: source repo clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
