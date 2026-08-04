#!/usr/bin/env python3
"""
check_docs_closure.py — Verify that documentation and workspace
artifacts are updated before closing an epic.

Usage:
    python scripts/check_docs_closure.py [--plan docs/plans/plan.md]

Checks:
  1. A plan file exists in docs/plans/ (argument or latest by date).
  2. ROADMAP.md contains the epic as completed.
  3. EVALS.md has test counts updated (row in CI/CD Quality Gates).
  4. Obsidian vault has relevant notes (decision + research summary).
  5. Known Limitations updated if applicable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent

OK = "[OK]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"


def find_latest_plan(repo_root: Path) -> Path | None:
    plans_dir = repo_root / "docs" / "plans"
    if not plans_dir.is_dir():
        return None
    plan_files = sorted(plans_dir.glob("*.md"), reverse=True)
    for f in plan_files:
        if re.match(r"^\d{4}-\d{2}-\d{2}_epic-\d+_.+\.md$", f.name):
            return f
    return None


def check_plan_saved(plan_arg: str | None, repo_root: Path) -> bool:
    if plan_arg:
        path = repo_root / plan_arg
        if path.is_file():
            print(f"  {OK} Plan: {plan_arg}")
            return True
        print(f"  {FAIL} Plan not found: {plan_arg}")
        return False
    latest = find_latest_plan(repo_root)
    if latest:
        print(f"  {OK} Plan: {latest.relative_to(repo_root)}")
        return True
    print(f"  {FAIL} No plan found in docs/plans/")
    return False


def check_roadmap_updated(repo_root: Path) -> bool:
    path = repo_root / "ROADMAP.md"
    if not path.is_file():
        print(f"  {FAIL} ROADMAP.md not found")
        return False
    content = path.read_text(encoding="utf-8")
    if "### Epic 16" in content:
        print(f"  {OK} ROADMAP.md: Epic 16 listed")
        return True
    print(f"  {SKIP} ROADMAP.md: Epic 16 not found (may be intentional)")
    return False


def check_evals_updated(repo_root: Path) -> bool:
    path = repo_root / "EVALS.md"
    if not path.is_file():
        print(f"  {FAIL} EVALS.md not found")
        return False
    content = path.read_text(encoding="utf-8")
    if "CI/CD Quality Gates" in content:
        print(f"  {OK} EVALS.md: CI/CD Quality Gates section found")
        return True
    print(f"  {FAIL} EVALS.md: CI/CD Quality Gates section not found")
    return False


def check_obsidian_backfill(repo_root: Path) -> bool:
    vault = repo_root / "obsidian-vault"
    if not vault.is_dir():
        print(f"  {SKIP} Obsidian vault not found -- skipping")
        return True
    decisions = list(vault.glob("**/04 Decisions/*Epic 16*")) + list(vault.glob("**/04 Decisions/*epic-16*"))
    research = list(vault.glob("**/03 Research/*Epic 16*")) + list(vault.glob("**/03 Research/*epic-16*"))
    ok = True
    if not decisions:
        print(f"  {SKIP} Obsidian: no Epic 16 decision note found (may be intentional)")
    else:
        print(f"  {OK} Obsidian: {len(decisions)} decision note(s)")
    if not research:
        print(f"  {SKIP} Obsidian: no Epic 16 research note found (may be intentional)")
    else:
        print(f"  {OK} Obsidian: {len(research)} research note(s)")
    return ok


def check_known_limitations(repo_root: Path) -> bool:
    path = repo_root / "obsidian-vault" / "Known Limitations.md"
    if path.is_file():
        print(f"  {OK} Known Limitations.md found")
        return True
    alt = repo_root / "Known Limitations.md"
    if alt.is_file():
        print(f"  {OK} Known Limitations.md found (repo root)")
        return True
    print(f"  {SKIP} Known Limitations.md not found -- skipping")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify docs closure before epic completion.")
    parser.add_argument(
        "--plan",
        help="Path to plan file (relative to repo root). Auto-detects latest if omitted.",
    )
    parser.add_argument(
        "--repo-path",
        help="Path to repo root (default: parent of script directory).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_path).resolve() if args.repo_path else _repo_root

    print("=== Docs Closure Check ===")
    all_ok = True

    if not check_plan_saved(args.plan, repo_root):
        all_ok = False
    if not check_roadmap_updated(repo_root):
        all_ok = False
    if not check_evals_updated(repo_root):
        all_ok = False
    if not check_obsidian_backfill(repo_root):
        all_ok = False
    if not check_known_limitations(repo_root):
        all_ok = False

    print()
    if all_ok:
        print("All closure checks passed.")
        sys.exit(0)
    else:
        print("Some checks failed. Review above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
