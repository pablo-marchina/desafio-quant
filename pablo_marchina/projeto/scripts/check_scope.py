#!/usr/bin/env python3
"""
check_scope.py — Detect changes in sensitive areas that require
contract/doc/EVALS updates.

Usage:
    python scripts/check_scope.py [--override FILE...]
        --override FILE    Skip check for a specific file (may repeat)

Behaviour:
  - Scans git diff (staged + unstaged) for changes in sensitive areas.
  - Sensitive areas: src/, tests/, docs/contracts/, docs/plans/,
    pyproject.toml, AGENTS.md, README.md, EVALS.md, ROADMAP.md
  - Requires at least one of these to be updated when a sensitive
    area changes (unless overridden):
      * docs/contracts/<module>_contract.md  (if src/<module>/ changes)
      * ROADMAP.md
      * EVALS.md
  - Exits 0 if all requirements met, 1 otherwise.
"""

from __future__ import annotations

import re
import subprocess
import sys

SENSITIVE_PREFIXES = [
    "src/",
    "tests/",
    "docs/contracts/",
    "docs/plans/",
    "pyproject.toml",
    "AGENTS.md",
    "README.md",
    "EVALS.md",
    "ROADMAP.md",
]

MODULE_CONTRACT_MAP: dict[re.Pattern, str] = {
    re.compile(r"^src/pipeline/"): "docs/contracts/pipeline_output_contract.md",
    re.compile(r"^src/rag/"): "docs/contracts/rag_contract.md",
    re.compile(r"^src/briefing/"): "docs/contracts/briefing_contract.md",
    re.compile(r"^src/scoring/"): "docs/contracts/scoring_contract.md",
    re.compile(r"^src/diagnosis/"): "docs/contracts/diagnosis_contract.md",
    re.compile(r"^src/recommendation/"): "docs/contracts/recommendation_contract.md",
    re.compile(r"^src/validation/"): "docs/contracts/evidence_contract.md",
}


def get_changed_files(repo_path: str | None = None) -> list[str]:
    kwargs = {}
    if repo_path:
        kwargs["cwd"] = repo_path

    # Unstaged changes to tracked files
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )
    # Staged changes
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )
    # Last commit (CI/PR scenarios)
    last = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1"],
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )
    # Untracked files
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )
    files = set()
    if result.returncode == 0:
        files.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    if staged.returncode == 0:
        files.update(line.strip() for line in staged.stdout.splitlines() if line.strip())
    if last.returncode == 0:
        files.update(line.strip() for line in last.stdout.splitlines() if line.strip())
    if untracked.returncode == 0:
        files.update(line.strip() for line in untracked.stdout.splitlines() if line.strip())
    return sorted(files)


def check_contracts(changed: list[str], overrides: set[str]) -> bool:
    errors: list[str] = []
    for path in changed:
        if any(path.startswith(p) for p in SENSITIVE_PREFIXES):
            for pattern, contract in MODULE_CONTRACT_MAP.items():
                if pattern.match(path):
                    if contract not in changed and contract not in overrides:
                        errors.append(
                            f"  {path} changes but {contract} is not "
                            f"updated.  Use --override {contract} to skip "
                            f"(with justification)."
                        )
    if errors:
        print("ERROR: Contract/documentation updates required:")
        for e in errors:
            print(e)
        return False
    return True


def check_docs_updated(changed: list[str], overrides: set[str]) -> bool:
    has_sensitive = any(path.startswith("src/") or path.startswith("tests/") for path in changed)
    if not has_sensitive:
        return True

    required_docs = ["ROADMAP.md", "EVALS.md"]
    missing = [d for d in required_docs if d not in changed and d not in overrides]
    if missing:
        print(
            "ERROR: Sensitive area changed but these docs are not updated:\n"
            + "\n".join(f"  {d}" for d in missing)
            + "\nUse --override <file> to skip (with justification)."
        )
        return False
    return True


def main() -> None:
    overrides = set()
    repo_path = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--override":
            i += 1
            if i < len(args):
                overrides.add(args[i])
        elif args[i] == "--repo-path":
            i += 1
            if i < len(args):
                repo_path = args[i]
        i += 1

    changed = get_changed_files(repo_path)

    if not changed:
        print("No changes detected.  OK.")
        sys.exit(0)

    print(f"Changed files ({len(changed)}):")
    for f in changed:
        print(f"  {f}")
    print()

    ok = True
    if not check_contracts(changed, overrides):
        ok = False
    if not check_docs_updated(changed, overrides):
        ok = False

    if ok:
        print("All scope checks passed.")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
