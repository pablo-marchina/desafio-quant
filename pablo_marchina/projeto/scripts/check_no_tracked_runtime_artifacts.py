"""Fail CI when generated runtime artifacts are committed to Git.

This guard complements .gitignore: ignored files that were already tracked remain
in Git until explicitly removed. Keeping the check in CI prevents cache, local
state, scraped payloads, build output, and local databases from re-entering the
production repository.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath


# These small, deterministic files are committed fixtures consumed by ingestion
# lifecycle tests. Everything else under staging/archive remains forbidden.
ALLOWED_TEST_FIXTURES = {
    "data/nvidia_corpus/archive/archive_test/20260610_120000_archive_test.md",
    "data/nvidia_corpus/archive/nim_test/20260610_120000_nim_test.md",
    "data/nvidia_corpus/staging/test_source/20260610T120000.md",
    "data/nvidia_corpus/staging/test_source/20260610T120000_meta.json",
}

FORBIDDEN_PREFIXES = (
    ".cache/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".venv/",
    "frontend/dist/",
    "frontend/node_modules/",
    "frontend/playwright-report/",
    "frontend/test-results/",
    "node_modules/",
    "reports/",
    "test_exports/",
    "data/product/exports/",
    "data/nvidia_corpus/archive/",
    "data/nvidia_corpus/staging/",
)

FORBIDDEN_EXACT_PATHS = {
    "frontend/tsconfig.tsbuildinfo",
    "data/product/product.db",
    "data/product/product.db-shm",
    "data/product/product.db-wal",
}

FORBIDDEN_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".tsbuildinfo",
    ".val",
)

LOCAL_DATABASE_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite3",
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    ]


def is_forbidden(path: str) -> bool:
    normalized = PurePosixPath(path).as_posix()
    lower = normalized.lower()

    if normalized in ALLOWED_TEST_FIXTURES:
        return False
    if normalized in FORBIDDEN_EXACT_PATHS:
        return True
    if lower.startswith(FORBIDDEN_PREFIXES):
        return True
    if lower.endswith(FORBIDDEN_SUFFIXES):
        return True
    if lower.startswith("data/product/") and lower.endswith(LOCAL_DATABASE_SUFFIXES):
        return True
    return False


def main() -> int:
    offenders = sorted(path for path in tracked_files() if is_forbidden(path))
    if not offenders:
        print("Tracked runtime artifact gate: PASS")
        return 0

    print("Tracked runtime artifact gate: FAIL", file=sys.stderr)
    print(
        "Remove generated/cache/local-state files from Git; keep them local via .gitignore:",
        file=sys.stderr,
    )
    for path in offenders:
        print(f"- {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
